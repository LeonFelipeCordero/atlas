//! Source guards and output-path validation.
use super::{
    config::MutationConfig,
    digest,
    formatting::{command_error, text},
};
use anyhow::{Result, bail};
use base64::{Engine, engine::general_purpose::STANDARD};
use serde_json::Value;
use std::{
    fs,
    path::{Component, Path, PathBuf},
};

pub fn working_directories(root: &Path, config: &MutationConfig) -> Result<Vec<PathBuf>> {
    config
        .targets
        .iter()
        .map(|(name, target)| {
            let path = resolve(&root.join(&target.cwd))?;
            if !path.starts_with(root) || !path.is_dir() {
                bail!("Invalid working directory for target {name}: {}", path.display());
            }
            Ok(path)
        })
        .collect()
}

/// Resolve existing symlinks while allowing missing output files, as Path.resolve does.
pub fn resolve(path: &Path) -> Result<PathBuf> {
    let absolute = std::path::absolute(path)?;
    let mut resolved = PathBuf::new();
    for component in absolute.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                resolved.pop();
            }
            _ => {
                resolved.push(component);
            }
        }
        match resolved.canonicalize() {
            Ok(path) => resolved = path,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(command_error(error, &resolved.to_string_lossy())),
        }
    }
    Ok(resolved)
}

pub fn prepare_output(root: &Path, manifests: &[Value], output: &Path) -> Result<PathBuf> {
    let mut protected = vec![resolve(&root.join("atlas.json"))?];
    for manifest in manifests {
        protected.push(resolve(&root.join(text(manifest, "path")))?);
    }
    if protected.iter().any(|path| path == output) {
        bail!("Mutation results cannot overwrite source files or atlas.json");
    }
    let mut logs = output.as_os_str().to_owned();
    logs.push(".logs");
    let logs = PathBuf::from(logs);
    if logs.is_symlink() {
        bail!("Mutation log directory must not be a symlink");
    }
    match fs::create_dir(&logs) {
        Ok(()) => {}
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists && logs.is_dir() => {}
        Err(error) => return Err(command_error(error, &logs.to_string_lossy())),
    }
    Ok(logs)
}

pub struct Source {
    pub path: PathBuf,
    original: Vec<u8>,
    pub modified: Vec<u8>,
    restored: bool,
}
impl Source {
    pub fn restore(&mut self) -> Result<()> {
        // A failed restoration aborts the campaign; do not silently retry in Drop.
        self.restored = true;
        fs::write(&self.path, &self.original).map_err(|error| command_error(error, &self.path.to_string_lossy()))?;
        Ok(())
    }
}
impl Drop for Source {
    fn drop(&mut self) {
        if !self.restored {
            let _ = fs::write(&self.path, &self.original);
        }
    }
}
pub fn source(root: &Path, manifest: &Value) -> Result<Source> {
    let name = text(manifest, "path");
    let relative = Path::new(name);
    let requested = root.join(relative);
    let path = requested.canonicalize().map_err(|error| command_error(error, &requested.to_string_lossy()))?;
    if relative.is_absolute()
        || relative.components().any(|part| part == Component::ParentDir)
        || !path.starts_with(root)
    {
        bail!("Unsafe mutation path: {name}");
    }
    let original = fs::read(&path).map_err(|error| command_error(error, &path.to_string_lossy()))?;
    let expected = STANDARD.decode(text(manifest, "originalBytes"))?;
    let start = manifest["span"]["startByte"].as_u64().and_then(|n| usize::try_from(n).ok());
    let end = manifest["span"]["endByte"].as_u64().and_then(|n| usize::try_from(n).ok());
    let valid = start.zip(end).filter(|&(start, end)| start < end && end <= original.len());
    let Some((start, end)) = valid else {
        bail!("Stale mutation source: {name}");
    };
    if digest(&original) != text(manifest, "sourceHash") || original[start..end] != expected {
        bail!("Stale mutation source: {name}");
    }
    let replacement = STANDARD.decode(text(manifest, "replacementBytes"))?;
    let modified = [&original[..start], replacement.as_slice(), &original[end..]].concat();
    Ok(Source { path, original, modified, restored: false })
}
