//! Actual native CLI regressions. Expected forms and errors were paired with Click's CLI oracle.
use atlas::bootstrap::{migrate_database, repository_service};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    path::PathBuf,
    process::{Command, Output},
};

struct Fixture {
    _root: tempfile::TempDir,
    database: PathBuf,
    project: String,
}
impl Fixture {
    fn new() -> Self {
        let root = tempfile::tempdir().unwrap();
        let database = root.path().join("graph.sqlite");
        let bytes = b"def brew():\n    return 1\n";
        std::fs::write(root.path().join("brew.py"), bytes).unwrap();
        migrate_database(Some(&database)).unwrap();
        let artifact = json!({"schemaVersion": 2, "repository": {"name": "Numeric", "path": root.path()},
            "nodes": [
                {"stableKey": "file:brew.py", "type": "file", "kind": "file", "level": "file", "name": "brew.py", "path": "brew.py", "properties": {"sha256": format!("{:x}", Sha256::digest(bytes)), "bytes": bytes.len()}},
                {"stableKey": "brew", "parentStableKey": "file:brew.py", "type": "function", "kind": "function", "level": "callable", "name": "brew", "path": "brew.py", "startLine": 1, "endLine": 2}
            ], "edges": []});
        let saved = repository_service(Some(&database)).unwrap().save_folder(root.path(), &artifact).unwrap();
        Self { _root: root, database, project: saved.repository_id }
    }
    fn invoke(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_atlas"))
            .env("DATABASE_PATH", &self.database)
            .env("COLUMNS", "80")
            .args(["graph", "--project", &self.project])
            .args(args)
            .output()
            .unwrap()
    }
}
fn payload(output: Output) -> Value {
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    assert!(output.stderr.is_empty());
    serde_json::from_slice(&output.stdout).unwrap()
}
#[test]
fn python_decimal_lexical_forms_reach_actual_navigation() {
    let fixture = Fixture::new();
    for (text, number) in [
        (" 1_0 ", 10),
        ("\t+2\n", 2),
        ("１００", 100),
        ("٢", 2),
        ("𝟚", 2),
        ("𝟤", 2),
        ("𝟮", 2),
        ("𝟸", 2),
        ("\u{85}١٠\u{a0}", 10),
    ] {
        assert_eq!(payload(fixture.invoke(&["find", "brew", "--limit", text]))["filters"]["limit"], number);
    }
    assert_eq!(payload(fixture.invoke(&["context", "brew", "--depth", "٢"]))["filters"]["depth"], 2);
    assert_eq!(payload(fixture.invoke(&["children", "file:brew.py", "--offset", " +０_１ "]))["nodes"], json!([]));
}
#[test]
fn relation_lists_strip_python_whitespace_and_normalize_each_part() {
    let fixture = Fixture::new();
    for whitespace in ['\u{1c}', '\u{1d}', '\u{1e}', '\u{1f}', '\u{85}', '\u{a0}', '\u{2003}'] {
        let relations = format!("{whitespace}calls{whitespace}, {whitespace}, references, CALLS");
        let result = payload(fixture.invoke(&["context", "brew", "--relations", &relations]));
        assert_eq!(result["filters"]["relations"], json!(["CALLS", "REFERENCES"]));
        let empty = fixture.invoke(&["context", "brew", "--relations", &whitespace.to_string()]);
        assert_eq!(empty.status.code(), Some(2));
        assert!(String::from_utf8(empty.stderr).unwrap().contains("Choose comma-separated relations"));
    }
}
#[test]
fn malformed_forms_and_bounded_overflow_use_clap_usage_errors() {
    let fixture = Fixture::new();
    for text in ["_1", "1_", "1__0", "²", "1.0", "0x10"] {
        let result = fixture.invoke(&["find", "brew", "--limit", text]);
        assert_eq!(result.status.code(), Some(2));
        assert!(result.stdout.is_empty());
        assert!(
            String::from_utf8(result.stderr)
                .unwrap()
                .contains(&format!("Invalid value for '--limit': '{text}' is not a valid integer range."))
        );
    }
    for (text, number) in [(" -０_１０ ".into(), "-10".into()), ("9".repeat(100), "9".repeat(100))] {
        let result = fixture.invoke(&["find", "brew", "--limit", &text]);
        assert_eq!(result.status.code(), Some(2));
        assert!(result.stdout.is_empty());
        assert!(
            String::from_utf8(result.stderr)
                .unwrap()
                .contains(&format!("Invalid value for '--limit': {number} is not in the range 1<=x<=100."))
        );
    }
}
#[test]
fn huge_source_start_lines_stay_exact_in_json_and_text() {
    let fixture = Fixture::new();
    for decimal in ["18446744073709551616".into(), "1234567890".repeat(50)] {
        check_huge_source(&fixture, &decimal);
    }
}
fn check_huge_source(fixture: &Fixture, decimal: &str) {
    let result = payload(fixture.invoke(&["source", "brew", "--start-line", decimal]));
    assert_eq!(result["filters"]["startLine"].to_string(), decimal);
    assert_eq!(result["source"]["startLine"].to_string(), decimal);
    assert_eq!(result["source"]["endLine"], 2);
    assert_eq!(result["source"]["lines"], json!([]));
    assert_eq!(result["source"]["nextStartLine"], Value::Null);
    assert_eq!(result["source"]["truncated"], false);
    let text = fixture.invoke(&["source", "brew", "--start-line", decimal, "--format", "text"]);
    assert!(text.status.success());
    assert!(text.stderr.is_empty());
    assert_eq!(String::from_utf8(text.stdout).unwrap().matches(&format!("\"startLine\": {decimal}")).count(), 2);
}
#[test]
fn sqlite_offset_overflow_fails_without_wrapping_to_another_page() {
    let fixture = Fixture::new();
    for value in ["9223372036854775808".into(), "18446744073709551616".into(), "9".repeat(100)] {
        let result = fixture.invoke(&["children", "file:brew.py", "--offset", &value]);
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert_eq!(
            serde_json::from_slice::<Value>(&result.stderr).unwrap(),
            json!({"error": "Python int too large to convert to SQLite INTEGER"})
        );
    }
}
