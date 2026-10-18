//! Shared access to Python fixtures and reference goldens for the dedicated language catalog.
use serde_json::Value;
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
};

pub fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/code_samples").canonicalize().unwrap()
}

pub fn snapshot(relative: &str) -> Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/snapshots").join(relative);
    serde_json::from_slice(&fs::read(&path).unwrap_or_else(|error| panic!("{}: {error}", path.display()))).unwrap()
}

pub fn assert_json(actual: &Value, expected: &Value, pointer: &str) {
    match (actual, expected) {
        (Value::Object(actual), Value::Object(expected)) => {
            assert_eq!(
                actual.keys().collect::<BTreeSet<_>>(),
                expected.keys().collect::<BTreeSet<_>>(),
                "keys at JSON pointer {pointer:?}"
            );
            for (key, value) in expected {
                let escaped = key.replace('~', "~0").replace('/', "~1");
                assert_json(&actual[key], value, &format!("{pointer}/{escaped}"));
            }
        }
        (Value::Array(actual), Value::Array(expected)) => {
            assert_eq!(actual.len(), expected.len(), "array length at JSON pointer {pointer:?}");
            for (index, (actual, expected)) in actual.iter().zip(expected).enumerate() {
                assert_json(actual, expected, &format!("{pointer}/{index}"));
            }
        }
        _ => assert_eq!(actual, expected, "value at JSON pointer {pointer:?}"),
    }
}
