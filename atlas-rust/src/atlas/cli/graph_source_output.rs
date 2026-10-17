use super::options::json_dump;
use serde_json::{Value, json};

pub fn source_text(payload: &Value) -> String {
    let mut metadata = payload.clone();
    metadata.as_object_mut().unwrap().shift_remove("source");
    metadata.as_object_mut().unwrap().shift_remove("sources");
    let mut sections = vec![json_dump(&metadata)];
    let excerpts = payload["sources"].as_array().cloned().unwrap_or_else(|| {
        let mut value = json!({"stableKey": payload["filters"]["key"]});
        value.as_object_mut().unwrap().extend(payload["source"].as_object().unwrap().clone());
        vec![value]
    });
    sections.extend(excerpts.iter().map(excerpt_text));
    sections.join("\n\n")
}
pub fn excerpt_text(excerpt: &Value) -> String {
    let mut details = excerpt.clone();
    details.as_object_mut().unwrap().shift_remove("lines");
    let name = excerpt["path"].as_str().or_else(|| excerpt["stableKey"].as_str()).unwrap_or("");
    let mut lines = vec![format!("### {name}"), json_dump(&details)];
    let start = excerpt["startLine"].as_u64().unwrap_or(1);
    if let Some(source) = excerpt["lines"].as_array() {
        lines.extend(
            source.iter().enumerate().map(|(i, line)| format!("{}: {}", start + i as u64, line.as_str().unwrap_or(""))),
        );
    }
    lines.join("\n")
}
