//! Sequential independent byte edits against trusted commands, without a baseline.
pub use super::matching::matching_targets;
use super::{
    config::MutationConfig,
    formatting::{command_error, error_suffix, io_error, python_json, repr, shell_join, text},
    process::{Interrupt, run_command},
    workspace::{prepare_output, resolve, source, working_directories},
};
use anyhow::Result;
use serde_json::{Value, json};
use std::{
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
    sync::Mutex,
    time::Instant,
};

static RUN_LOCK: Mutex<()> = Mutex::new(());

pub struct MutationRunner<'a> {
    root: PathBuf,
    config: &'a MutationConfig,
    directories: Vec<PathBuf>,
}
impl<'a> MutationRunner<'a> {
    /// Validate every working directory before touching sources or output.
    pub fn new(root: &Path, config: &'a MutationConfig) -> Result<Self> {
        config.validate()?;
        let root = root.canonicalize()?;
        let directories = working_directories(&root, config)?;
        Ok(Self { root, config, directories })
    }

    pub fn run(&self, manifests: &[Value], output: &Path) -> Result<Value> {
        self.run_with_progress(manifests, output, &mut |_| {})
    }

    /// SIGINT/SIGTERM stop commands and restore source before returning an error.
    /// SIGKILL and machine failure cannot be recovered. Commands are trusted.
    pub fn run_with_progress(
        &self,
        manifests: &[Value],
        output: &Path,
        progress: &mut dyn FnMut(&str),
    ) -> Result<Value> {
        let _lock = RUN_LOCK.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        let started = Instant::now();
        let output = resolve(output)?;
        let logs = prepare_output(&self.root, manifests, &output)?;
        let mapped =
            manifests.iter().filter(|item| !matching_targets(text(item, "path"), self.config).is_empty()).count();
        progress(&format!(
            "Planned {} mutations: {mapped} mapped, {} unmapped",
            manifests.len(),
            manifests.len() - mapped
        ));
        progress(&format!("Results: {}; command logs: {}", output.display(), logs.display()));
        let interrupt = Interrupt::new()?;
        let mut campaign = Campaign { runner: self, logs, interrupt: &interrupt, progress };
        let mut stream = File::create(&output).map_err(|error| command_error(error, &output.to_string_lossy()))?;
        let mut counts = json!({});
        for (ordinal, manifest) in manifests.iter().enumerate() {
            interrupt.check()?;
            let label = format!(
                "[{}/{}] {}:{} {}",
                ordinal + 1,
                manifests.len(),
                text(manifest, "path"),
                manifest["span"]["startLine"],
                text(manifest, "ruleId")
            );
            (campaign.progress)(&format!(
                "{label}: {} -> {}",
                repr(text(manifest, "originalText")),
                repr(text(manifest, "replacement"))
            ));
            let result = campaign.execute(manifest, ordinal)?;
            writeln!(stream, "{}", python_json(&result)).map_err(io_error)?;
            stream.flush().map_err(io_error)?;
            let outcome = result["outcome"].as_str().unwrap();
            counts[outcome] = json!(counts[outcome].as_u64().unwrap_or(0) + 1);
            (campaign.progress)(&format!("{label}: {outcome}{}", error_suffix(&result)));
        }
        (campaign.progress)(&format!(
            "Completed {} mutations in {:.2}s: {}",
            manifests.len(),
            started.elapsed().as_secs_f64(),
            python_json(&counts)
        ));
        Ok(counts)
    }
}

struct Campaign<'a, 'b> {
    runner: &'a MutationRunner<'a>,
    logs: PathBuf,
    interrupt: &'a Interrupt,
    progress: &'b mut dyn FnMut(&str),
}
impl Campaign<'_, '_> {
    fn execute(&mut self, manifest: &Value, ordinal: usize) -> Result<Value> {
        let mut result = json!({"manifestId": manifest["id"], "path": manifest["path"], "ruleId": manifest["ruleId"],
            "outcome": "unmapped", "targets": []});
        if matching_targets(text(manifest, "path"), self.runner.config).is_empty() {
            return Ok(result);
        }
        let mut source = match source(&self.runner.root, manifest) {
            Ok(source) => source,
            Err(error) => {
                set_error(&mut result, error);
                return Ok(result);
            }
        };
        let execution = (|| -> Result<()> {
            self.interrupt.check()?;
            fs::write(&source.path, &source.modified)
                .map_err(|error| command_error(error, &source.path.to_string_lossy()))?;
            self.execute_targets(manifest, ordinal, &mut result)
        })();
        source.restore()?;
        (self.progress)(&format!("Source restored: {}", text(manifest, "path")));
        self.interrupt.check()?;
        if let Err(error) = execution {
            if error.is::<super::process::InvalidCommand>() {
                return Err(error);
            }
            set_error(&mut result, error);
            return Ok(result);
        }
        let outcome = ["killed", "error", "timeout", "survived"]
            .into_iter()
            .find(|outcome| result["targets"].as_array().unwrap().iter().any(|item| item["outcome"] == *outcome))
            .unwrap();
        result["outcome"] = json!(outcome);
        Ok(result)
    }

    fn execute_targets(&mut self, manifest: &Value, ordinal: usize, result: &mut Value) -> Result<()> {
        let targets = matching_targets(text(manifest, "path"), self.runner.config);
        for (index, (name, _)) in targets.iter().enumerate() {
            let log = self.logs.join(format!("{ordinal}-{index}.log"));
            let execution = self.run_target(name, &log)?;
            result["targets"].as_array_mut().unwrap().push(execution);
        }
        Ok(())
    }

    fn run_target(&mut self, name: &str, log: &Path) -> Result<Value> {
        let position = self.runner.config.targets.get_index_of(name).unwrap();
        let target = &self.runner.config.targets[name];
        let cwd = &self.runner.directories[position];
        (self.progress)(&format!(
            "Running target {name}: {} (cwd={}, timeout={}s, log={})",
            shell_join(&target.command),
            cwd.display(),
            target.timeout_seconds,
            log.display()
        ));
        let execution = run_command(target, (cwd, log), self.interrupt)?;
        let exit = execution["exitCode"].as_i64().map(|n| n.to_string()).unwrap_or_else(|| "None".into());
        (self.progress)(&format!(
            "Target {name}: {} (exit={exit}, {:.2}s){}",
            text(&execution, "outcome"),
            execution["durationSeconds"].as_f64().unwrap(),
            error_suffix(&execution)
        ));
        let mut named = json!({"name": name});
        named.as_object_mut().unwrap().extend(execution.as_object().unwrap().clone());
        Ok(named)
    }
}
fn set_error(result: &mut Value, error: anyhow::Error) {
    result["outcome"] = json!("error");
    result["error"] = json!(error.to_string());
}
