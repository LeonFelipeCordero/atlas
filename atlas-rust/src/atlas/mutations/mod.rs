//! Verified mutation manifests and opt-in, restoring command execution.
pub mod config;
mod formatting;
pub mod manifests;
pub mod matching;
mod process;
pub mod report;
pub mod rules;
pub mod runner;
mod workspace;

use serde_json::Value;
use sha2::{Digest, Sha256};

pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

/// Python json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False).
pub fn canonical_json(value: &Value) -> String {
    match value {
        Value::Object(object) => {
            let mut keys: Vec<_> = object.keys().collect();
            keys.sort();
            let fields: Vec<_> = keys
                .iter()
                .map(|key| format!("{}:{}", serde_json::to_string(key).unwrap(), canonical_json(&object[*key])))
                .collect();
            format!("{{{}}}", fields.join(","))
        }
        Value::Array(items) => format!("[{}]", items.iter().map(canonical_json).collect::<Vec<_>>().join(",")),
        _ => value.to_string(),
    }
}

#[cfg(test)]
mod runner_process_tests;
#[cfg(test)]
mod runner_tests;
#[cfg(test)]
mod tests;
