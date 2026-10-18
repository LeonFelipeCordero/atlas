//! Run trusted mutation targets in the current workspace; stdout is JSON only.
use super::options::Options;
use crate::mutations::{config, report::build_mutation_report, runner};
use anyhow::{Result, bail};
use serde_json::json;
use std::path::Path;

fn progress(message: &str) {
    eprintln!("[mutations] {message}");
}

fn ascii_json(value: &serde_json::Value) -> Result<String> {
    let text = serde_json::to_string_pretty(value)?;
    Ok(text
        .chars()
        .map(|character| {
            if character.is_ascii() {
                return character.to_string();
            }
            character.encode_utf16(&mut [0; 2]).iter().map(|unit| format!("\\u{unit:04x}")).collect()
        })
        .collect())
}

pub fn run(parent: &Options, args: &[String]) -> Result<i32> {
    let options = Options::parse("mutations run", args, (&["--folder", "--output", "--target"], &["--help"]))?;
    if options.has("--help") {
        super::help::print("mutations run", false);
        return Ok(0);
    }
    options.arguments(&[], false)?;
    let root = crate::paths::absolute_path(Path::new(options.get("--folder", parent.get("--folder", "."))))?;
    progress(&format!("Loading configuration: {}", root.join("atlas.json").display()));
    let mut project = crate::metrics::config::load_project_config(&root)?;
    // Validate the full configuration before selecting a subset of targets.
    let _ = config::from_project(&project)?;
    if project["mutations"]["targets"].as_object().is_none_or(|targets| targets.is_empty()) {
        bail!("Configure mutations.targets in atlas.json before running mutations");
    }
    if !super::mutation_targets::select(&mut project, &options)? {
        return Ok(1);
    }
    let config = config::from_project(&project)?;
    let names = project["mutations"]["targets"].as_object().unwrap().keys().cloned().collect::<Vec<_>>();
    progress(&format!("Selected targets: {}", names.join(", ")));
    let saved = parent.has("--saved");
    progress(&format!(
        "{} {}",
        if saved { "Reading saved candidates for" } else { "Analyzing source files in" },
        root.display()
    ));
    let mut report = if saved {
        crate::services::repositories::saved_folder_report(&root)?
    } else {
        crate::metrics::report::build_artifact_report(&crate::indexer::analyze_repository(&root)?)?
    };
    let candidates = report["mutationCandidates"].as_array_mut().unwrap();
    candidates.retain(|item| !runner::matching_targets(item["path"].as_str().unwrap_or(""), &config).is_empty());
    progress(&format!(
        "Found {} candidate sites in selected targets; generating configured replacements",
        candidates.len()
    ));
    let planned = build_mutation_report(&root, &report, &config)?;
    let destination = root.join(options.get("--output", "mutation-results.jsonl"));
    let execution = runner::MutationRunner::new(&root, &config)?.run_with_progress(
        planned["mutations"].as_array().unwrap(),
        &destination,
        &mut progress,
    );
    let counts = match execution {
        Err(error) if error.to_string() == "Mutation run interrupted" => {
            eprintln!("\nAborted!");
            return Ok(1);
        }
        result => result?,
    };
    println!("{}", ascii_json(&json!({"output": crate::paths::absolute_path(&destination)?, "counts": counts}))?);
    Ok(0)
}
