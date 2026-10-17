//! Mutation manifests are derived only. Never save a graph or change source.
use super::options::Options;
use crate::mutations::{config, report::build_mutation_report, rules::REGISTRY};
use anyhow::Result;
use serde_json::{Value, json};
use std::path::Path;

fn options(args: &[String]) -> Result<Options> {
    let options = Options::parse("mutations", args, (&["--folder"], &["--saved", "--rules", "--help"]))?;
    if !options.has("--help") {
        options.arguments(&[], false)?;
    }
    Ok(options)
}

fn output(options: &Options) -> Result<Value> {
    if options.has("--rules") {
        return Ok(json!({"rules": &*REGISTRY}));
    }
    let root = crate::persistence::database::absolute_path(Path::new(options.get("--folder", ".")))?;
    let project = crate::metrics::config::load_project_config(&root)?;
    let config = config::from_project(&project)?;
    let report = if options.has("--saved") {
        crate::services::repositories::saved_folder_report(&root)?
    } else {
        crate::metrics::report::build_artifact_report(&crate::indexer::analyze_repository(&root)?)?
    };
    build_mutation_report(&root, &report, &config)
}

/// Arguments exclude the `mutations` command name. Errors propagate to the CLI boundary.
pub fn run(args: &[String]) -> Result<i32> {
    let options = options(args)?;
    if options.has("--help") {
        super::help::print("mutations", false);
        return Ok(0);
    }
    println!("{}", serde_json::to_string_pretty(&output(&options)?)?);
    Ok(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn help_tokens_are_flags_only_outside_values_and_literal_arguments() {
        let value = options(&["--folder".into(), "--help".into()]).unwrap();
        assert_eq!(value.get("--folder", "."), "--help");
        assert!(!value.has("--help"));
        assert_eq!(
            options(&["--".into(), "--help".into()]).err().unwrap().to_string(),
            "Got unexpected extra argument (--help)"
        );
        assert!(options(&["--help".into()]).unwrap().has("--help"));
    }
    #[test]
    fn rules_bypass_every_boundary() -> Result<()> {
        let args = ["--folder", "/missing-folder", "--rules", "--saved"].map(String::from);
        assert_eq!(output(&options(&args)?)?, json!({"rules": &*REGISTRY}));
        Ok(())
    }
    #[test]
    fn saved_candidates_match_live_and_reject_stale_sources() -> Result<()> {
        let root = tempfile::tempdir()?;
        let path = root.path().join("brew.py");
        let bytes = b"def brew(a):\n    return a + 2\n";
        std::fs::write(&path, bytes)?;
        let source = crate::domain::models::SourceFile {
            path: "brew.py".into(),
            absolute_path: path.clone(),
            language: "python".into(),
            source: bytes.to_vec(),
        };
        let found = crate::parsing::mutation_candidates::extract_candidates(&source)?;
        let artifact = json!({"schemaVersion": 2, "repository": {"name": "coffee", "path": root.path()}, "edges": [], "diagnostics": [],
            "nodes": [{"stableKey": "file:brew.py", "type": "file", "kind": "file", "level": "file", "name": "brew.py", "path": "brew.py", "language": "python", "properties": {}}],
            "mutationCandidates": found});
        let db = root.path().join("graph.sqlite");
        crate::bootstrap::migrate_database(Some(&db))?;
        let mut service = crate::bootstrap::repository_service(Some(&db))?;
        service.save_folder(root.path(), &artifact)?;
        let project = service.list()?.remove(0);
        let saved = service.report(&project.name)?;
        let config = config::MutationConfig { rules: vec!["arithmetic.add-to-subtract".into()] };
        let expected = build_mutation_report(root.path(), &artifact, &config)?;
        assert_eq!(expected["mutations"].as_array().unwrap().len(), 1);
        assert_eq!(build_mutation_report(root.path(), &saved, &config)?, expected);
        assert_eq!(std::fs::read(&path)?, bytes);
        std::fs::write(&path, b"# changed\n")?;
        let error = build_mutation_report(root.path(), &saved, &config::MutationConfig::default()).unwrap_err();
        assert!(error.to_string().starts_with("Stale or invalid mutation candidate"));
        Ok(())
    }

    #[test]
    fn folder_aliases_and_help() -> Result<()> {
        for flag in ["-f", "--f", "--folder"] {
            let args = [flag, "~/sub/..", "--saved"].map(String::from);
            let options = options(&args)?;
            assert_eq!(options.get("--folder", "."), "~/sub/..");
            assert!(options.has("--saved"));
        }
        assert!(super::super::help::text("mutations").contains("mutations.rules is a list of rule IDs"));
        Ok(())
    }
}
