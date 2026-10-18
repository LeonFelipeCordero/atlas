//! Source discovery with nested Git and Atlas ignore rules, without Git.
use super::catalog::LANGUAGES;
use super::ignore_spec::IgnoreSpec;
use crate::domain::models::SourceFile;
use anyhow::{Context, Result, anyhow, bail};
#[path = "discovery_open.rs"]
mod discovery_open;
use discovery_open::SourceRoot;
use std::{
    collections::HashSet,
    fs,
    path::{Path, PathBuf},
    sync::OnceLock,
};

pub const EXCLUDED_LANGUAGES: &[&str] = &["c", "cpp", "csharp", "php", "phpdoc", "ruby", "rbs"];
pub const IGNORED_DIRECTORIES: &[&str] = &[
    ".git",
    ".idea",
    ".next",
    ".output",
    ".venv",
    "build",
    "coverage",
    "deps",
    "dist",
    "node_modules",
    "target",
    "vendor",
];

pub fn supported_languages() -> &'static HashSet<String> {
    static CATALOG: OnceLock<HashSet<String>> = OnceLock::new();
    CATALOG.get_or_init(|| {
        LANGUAGES
            .iter()
            .map(|s| s.to_string())
            .chain(tree_sitter_language_pack::available_languages())
            .filter(|s| !EXCLUDED_LANGUAGES.contains(&s.as_str()))
            .collect()
    })
}

pub fn is_supported_language(language: &str) -> bool {
    supported_languages().contains(language)
}

pub fn require_supported_language(language: &str) -> Result<()> {
    if !is_supported_language(language) {
        bail!("Unsupported Python importer language: {language}");
    }
    Ok(())
}

pub fn validate_repository(root: &Path) -> Result<PathBuf> {
    let resolved = resolve_path(root, 0)?;
    if !metadata(&resolved)?.is_some_and(|info| info.is_dir()) {
        bail!("Repository does not exist: {}", resolved.display());
    }
    Ok(resolved)
}

fn resolve_path(path: &Path, depth: usize) -> Result<PathBuf> {
    if depth > 64 {
        bail!("Symlink loop while resolving {}", path.display());
    }
    let absolute = std::path::absolute(path)?;
    let mut resolved = PathBuf::new();
    for component in absolute.components() {
        resolve_component(&mut resolved, component, depth)?;
    }
    Ok(resolved)
}

fn resolve_component(resolved: &mut PathBuf, component: std::path::Component<'_>, depth: usize) -> Result<()> {
    use std::path::Component;
    match component {
        Component::ParentDir => {
            resolved.pop();
        }
        Component::CurDir => {}
        component => resolved.push(component.as_os_str()),
    }
    resolve_symlink(resolved, depth)
}

fn resolve_symlink(resolved: &mut PathBuf, depth: usize) -> Result<()> {
    let info = match fs::symlink_metadata(&*resolved) {
        Ok(info) => Some(info),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
        Err(error) => return Err(error).with_context(|| format!("Cannot inspect path {}", resolved.display())),
    };
    if info.is_some_and(|info| info.is_symlink()) {
        let target = fs::read_link(&*resolved)?;
        let target =
            if target.is_absolute() { target } else { resolved.parent().unwrap_or(Path::new("/")).join(target) };
        *resolved = resolve_path(&target, depth + 1)?;
    }
    Ok(())
}

pub fn detect_language(path: &Path) -> Option<String> {
    let name = path.file_name()?.to_str()?;
    let language = tree_sitter_language_pack::detect_language_from_path(name)?;
    is_supported_language(language).then(|| language.to_owned())
}

#[derive(Clone)]
struct Rules {
    base: PathBuf,
    spec: IgnoreSpec,
}

fn metadata(path: &Path) -> Result<Option<fs::Metadata>> {
    match fs::metadata(path) {
        Ok(info) => Ok(Some(info)),
        // Broken and self-looping symlinks are intentionally absent from discovery.
        Err(error) if error.kind() == std::io::ErrorKind::NotFound || error.raw_os_error() == Some(libc::ELOOP) => {
            Ok(None)
        }
        Err(error) => Err(error).with_context(|| format!("Cannot inspect path {}", path.display())),
    }
}

fn directory_rules(base: &Path, inherited: &[Rules], filename: &str) -> Result<Vec<Rules>> {
    let mut rules = inherited.to_vec();
    let path = base.join(filename);
    if metadata(&path)?.is_some_and(|info| info.is_file()) {
        let content = fs::read_to_string(&path)?;
        rules.push(Rules { base: base.to_owned(), spec: IgnoreSpec::new(&content)? });
    }
    Ok(rules)
}

fn is_ignored(path: &Path, rules: &[Rules], is_dir: bool) -> bool {
    let mut ignored = false;
    for rule in rules {
        let relative = path.strip_prefix(&rule.base).unwrap_or(path).to_string_lossy();
        let relative = format!("{relative}{}", if is_dir { "/" } else { "" });
        if let Some(include) = rule.spec.check_file(&relative) {
            ignored = include;
        }
    }
    ignored
}

#[derive(Clone)]
struct DirectoryContext {
    base: PathBuf,
    git: Vec<Rules>,
    atlas: Vec<Rules>,
    use_gitignore: bool,
}

impl DirectoryContext {
    fn include_directory(&self, path: &Path) -> bool {
        let name = path.file_name().unwrap_or_default().to_string_lossy();
        if name == ".git" || is_ignored(path, &self.atlas, true) {
            return false;
        }
        if self.use_gitignore {
            return !is_ignored(path, &self.git, true);
        }
        !IGNORED_DIRECTORIES.contains(&name.as_ref()) && !name.contains("generated")
    }
    fn include_file(&self, path: &Path) -> bool {
        path.file_name().is_some_and(|name| name != ".git")
            && !is_ignored(path, &self.git, false)
            && !is_ignored(path, &self.atlas, false)
    }
    fn load_rules(&mut self) -> Result<()> {
        if self.use_gitignore {
            self.git = directory_rules(&self.base, &self.git, ".gitignore")?;
        }
        self.atlas = directory_rules(&self.base, &self.atlas, ".atlasignore")?;
        Ok(())
    }
}

fn walk_directory(mut context: DirectoryContext, paths: &mut Vec<PathBuf>) -> Result<()> {
    context.load_rules()?;
    let entries =
        fs::read_dir(&context.base).with_context(|| format!("Cannot scan directory {}", context.base.display()))?;
    for entry in entries {
        visit_entry(entry?.path(), &context, paths)?;
    }
    Ok(())
}

fn visit_entry(path: PathBuf, context: &DirectoryContext, paths: &mut Vec<PathBuf>) -> Result<()> {
    let Some(info) = metadata(&path)? else { return Ok(()) };
    if !info.is_dir() {
        if context.include_file(&path) {
            paths.push(path);
        }
        return Ok(());
    }
    if context.include_directory(&path) && !fs::symlink_metadata(&path)?.is_symlink() {
        let child = DirectoryContext { base: path, ..context.clone() };
        walk_directory(child, paths)?;
    }
    Ok(())
}

pub fn repository_paths(root: &Path) -> Result<Vec<PathBuf>> {
    let root = resolve_path(root, 0)?;
    let mut paths = vec![];
    let context = DirectoryContext {
        base: root.clone(),
        git: vec![],
        atlas: vec![],
        use_gitignore: metadata(&root.join(".gitignore"))?.is_some_and(|info| info.is_file()),
    };
    walk_directory(context, &mut paths)?;
    let mut contained = vec![];
    for path in paths {
        if metadata(&path)?.is_some_and(|info| info.is_file()) && fs::canonicalize(&path)?.starts_with(&root) {
            contained.push(path);
        }
    }
    Ok(contained)
}

pub fn discover_files(root: &Path) -> Result<Vec<SourceFile>> {
    let root = resolve_path(root, 0)?;
    let source_root = SourceRoot::new(&root)?;
    let mut paths = repository_paths(&root)?;
    paths.sort();
    let mut files = Vec::new();
    for path in paths {
        let Some(language) = detect_language(&path) else { continue };
        let Some(source) = source_root.read(&path)? else { continue };
        files.push(SourceFile {
            path: path
                .strip_prefix(&root)
                .map_err(|e| anyhow!(e))?
                .to_string_lossy()
                .replace(std::path::MAIN_SEPARATOR, "/"),
            source,
            absolute_path: path,
            language,
        });
    }
    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn catalog_excludes_companion_and_unsupported_grammars() {
        for language in EXCLUDED_LANGUAGES {
            assert!(!is_supported_language(language));
        }
        assert!(is_supported_language("ziggy_schema"));
        assert_eq!(detect_language(Path::new("file.py")).as_deref(), Some("python"));
        assert_eq!(detect_language(Path::new("file.cpp")), None);
        assert_eq!(detect_language(Path::new(".gitignore")), None);
        assert_eq!(detect_language(Path::new("Makefile")), None);
    }
    #[test]
    fn validation_resolves_missing_parent_segments() -> Result<()> {
        let temp = tempfile::tempdir()?;
        assert_eq!(validate_repository(&temp.path().join("missing/.."))?, temp.path());
        assert!(validate_repository(&temp.path().join("missing")).is_err());
        Ok(())
    }
    #[cfg(unix)]
    #[test]
    fn symlinks_keep_internal_spelling_but_cannot_escape_root() -> Result<()> {
        use std::os::unix::fs::symlink;
        let temp = tempfile::tempdir()?;
        let outside = tempfile::tempdir()?;
        fs::write(temp.path().join("main.py"), "run()")?;
        fs::write(outside.path().join("outside.py"), "hidden()")?;
        symlink(temp.path().join("main.py"), temp.path().join("alias.py"))?;
        symlink(outside.path().join("outside.py"), temp.path().join("outside.py"))?;
        symlink(temp.path(), temp.path().join("cycle"))?;
        symlink("loop.py", temp.path().join("loop.py"))?;
        symlink("missing.py", temp.path().join("dangling.py"))?;
        let files = discover_files(temp.path())?;
        assert_eq!(files.iter().map(|f| f.path.as_str()).collect::<Vec<_>>(), ["alias.py", "main.py"]);
        Ok(())
    }
    #[test]
    fn character_class_double_hyphens_are_not_set_subtraction() -> Result<()> {
        let temp = tempfile::tempdir()?;
        fs::write(temp.path().join(".gitignore"), "[a-z--x].py\n")?;
        fs::write(temp.path().join("x.py"), "run()")?;
        assert!(discover_files(temp.path())?.is_empty());
        Ok(())
    }
    #[test]
    fn nested_ignore_and_default_directory_modes() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path();
        fs::create_dir(root.join("node_modules"))?;
        fs::write(root.join("node_modules/a.py"), "run()")?;
        fs::write(root.join("main.py"), "run()")?;
        assert_eq!(discover_files(root)?.len(), 1);
        fs::write(root.join(".gitignore"), "*.py\n!main.py\n")?;
        fs::write(root.join("node_modules/.gitignore"), "!a.py\n")?;
        assert_eq!(discover_files(root)?.iter().filter(|f| f.language == "python").count(), 2);
        fs::write(root.join(".atlasignore"), "node_modules/\n")?;
        assert_eq!(discover_files(root)?.iter().filter(|f| f.language == "python").count(), 1);
        Ok(())
    }
}
