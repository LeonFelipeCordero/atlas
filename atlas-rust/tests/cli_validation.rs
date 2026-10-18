//! Native clap validation and runtime error regressions through the executable.
use std::process::{Command, Output};

fn invoke(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_atlas")).env("COLUMNS", "80").args(args).output().unwrap()
}
fn usage_error(args: &[&str], marker: &str) {
    let output = invoke(args);
    assert_eq!(output.status.code(), Some(2), "{args:?}: {output:?}");
    assert!(output.stdout.is_empty());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains(marker), "{args:?}: {stderr}");
    assert!(stderr.contains("--help"), "{args:?}: {stderr}");
}

#[test]
fn competing_invalid_options_and_argument_counts_fail_before_execution() {
    for args in [
        vec!["graph", "find", "brew", "--limit", "bad", "--bogus"],
        vec!["graph", "find", "brew", "--bogus", "--limit", "bad"],
        vec!["graph", "path", "--max-depth", "bad"],
        vec!["graph", "overview", "extra", "--bogus"],
        vec!["report", "--format", "yaml", "--bogus"],
        vec!["graph", "context", "brew", "--depth", "bad", "--direction", "wrong"],
    ] {
        usage_error(&args, "error:");
    }
}

#[test]
fn repeated_options_use_last_value_and_still_require_arguments() {
    usage_error(&["graph", "context", "brew", "--depth", "2", "--depth=-1"], "-1 is not in the range");
    usage_error(&["graph", "context", "brew", "--depth", "-1", "--direction", "bad", "--depth=2"], "--direction");
    usage_error(&["graph", "find", "--limit", "0", "--limit=1"], "<QUERY>");
}

#[test]
fn help_bypasses_numeric_validation() {
    let output = invoke(&["graph", "find", "--limit", "0", "--help"]);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    assert!(String::from_utf8(output.stdout).unwrap().contains("Usage: atlas graph find"));
}

#[test]
fn quoted_and_control_values_fail_safely() {
    for value in ["a'b", "a\"b", "a\\b", "a\nb", "a\tb", "a\rb", "a\u{1b}b"] {
        for command in ["report", "check"] {
            usage_error(&[command, "--format", value], "--format");
        }
        usage_error(&[value], "error:");
        usage_error(&["graph", "find", "brew", "--limit", value], "--limit");
    }
}

#[test]
fn missing_database_has_sqlalchemy_style_connection_error_without_creating_files() {
    let root = tempfile::tempdir().unwrap();
    let database = root.path().join("absent").join("graph.sqlite");
    let output = Command::new(env!("CARGO_BIN_EXE_atlas"))
        .env("DATABASE_PATH", &database)
        .args(["graph", "overview"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert_eq!(
        serde_json::from_slice::<serde_json::Value>(&output.stderr).unwrap(),
        serde_json::json!({"error": format!(
            "Cannot read graph database {}: (sqlite3.OperationalError) unable to open database file\n(Background on this error at: https://sqlalche.me/e/21/e3q8). Index the project after explicitly migrating the database.", database.display()
        )})
    );
    assert!(!database.parent().unwrap().exists());
}

#[test]
fn config_read_failure_includes_config_path() {
    let root = tempfile::tempdir().unwrap();
    let file = root.path().join("README.md");
    std::fs::write(&file, "not a directory").unwrap();
    let output = invoke(&["check", "-f", file.to_str().unwrap()]);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert!(String::from_utf8(output.stderr).unwrap().contains(file.join("atlas.json").to_str().unwrap()));
}
