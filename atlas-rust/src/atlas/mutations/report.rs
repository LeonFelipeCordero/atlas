//! JSON manifests and the exact metrics Markdown candidate section.
use super::{config::MutationConfig, manifests::generate_manifest_values};
use anyhow::{Result, anyhow};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path};

pub fn build_mutation_report(root: &Path, report: &Value, config: &MutationConfig) -> Result<Value> {
    let candidates = report
        .get("mutationCandidates")
        .and_then(Value::as_array)
        .ok_or_else(|| anyhow!("Missing or invalid mutationCandidates"))?;
    Ok(json!({"schemaVersion": 1, "mutations": generate_manifest_values(root, candidates, &config.rules)?}))
}

pub fn code(value: &str) -> String {
    let value = value.replace(['\n', '\r'], " ").replace('|', "\\|");
    let mut fence = "`".to_owned();
    while value.contains(&fence) {
        fence.push('`');
    }
    let padding = if value.starts_with('`') || value.ends_with('`') { " " } else { "" };
    format!("{fence}{padding}{value}{padding}{fence}")
}

/// Return an empty string for absent or empty candidates, with no trailing newline.
pub fn render_candidates_markdown(report: &Value) -> String {
    let Some(candidates) = report.get("mutationCandidates").and_then(Value::as_array).filter(|items| !items.is_empty())
    else {
        return String::new();
    };
    let mut counts = BTreeMap::new();
    for candidate in candidates {
        *counts.entry(candidate["kind"].as_str().unwrap_or("")).or_insert(0) += 1;
    }
    let counts = counts.iter().map(|(kind, count)| format!("{kind}: {count}")).collect::<Vec<_>>().join(", ");
    let mut rows = vec![
        "## Mutation candidates".into(),
        String::new(),
        "Identified source sites only; no mutations generated or tests executed.".into(),
        String::new(),
        counts,
        String::new(),
        "| Location (byte columns) | Kind | Operator | Original source |".into(),
        "| --- | --- | --- | --- |".into(),
    ];
    for item in candidates {
        let location = format!(
            "{}:{}:{}",
            item["path"].as_str().unwrap_or(""),
            item["span"]["startLine"],
            item["span"]["startColumn"]
        );
        let operator = item["operator"].as_str().filter(|value| !value.is_empty()).unwrap_or("—");
        let cells =
            [&location, item["kind"].as_str().unwrap_or(""), operator, item["originalText"].as_str().unwrap_or("")];
        rows.push(format!("| {} |", cells.iter().map(|cell| code(cell)).collect::<Vec<_>>().join(" | ")));
    }
    rows.join("\n")
}
