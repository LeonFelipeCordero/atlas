//! Click parameter processing and error rendering regressions, through the native executable.
use std::process::{Command, Output};

type InvalidOption<'a> = (&'a str, &'a str, &'a str);

fn invoke(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_atlas")).env("COLUMNS", "80").args(args).output().unwrap()
}
fn usage_error(args: &[&str], message: &str) {
    let output = invoke(args);
    assert_eq!(output.status.code(), Some(2), "{args:?}: {output:?}");
    assert!(output.stdout.is_empty());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.ends_with(&format!("Error: {message}\n")), "{args:?}: {stderr}");
}

#[test]
fn explicit_options_follow_first_occurrence_order_before_arguments() {
    let commands: &[(&str, &[InvalidOption<'_>])] = &[
        ("find", &[("--limit", "0", "0 is not in the range 1<=x<=100.")]),
        (
            "children",
            &[("--limit", "0", "0 is not in the range 1<=x<=100."), ("--offset", "-1", "-1 is not in the range x>=0.")],
        ),
        (
            "context",
            &[
                ("--depth", "-1", "-1 is not in the range 0<=x<=20."),
                ("--direction", "bad", "'bad' is not one of 'out', 'in', 'both'."),
                (
                    "--relations",
                    "bad",
                    "Choose comma-separated relations from CONTAINS, CALLS, REFERENCES, IMPORTS, INHERITS",
                ),
                ("--max-nodes", "0", "0 is not in the range 1<=x<=300."),
                ("--max-edges", "0", "0 is not in the range 1<=x<=1000."),
            ],
        ),
        (
            "path",
            &[
                ("--max-depth", "-1", "-1 is not in the range 0<=x<=20."),
                ("--direction", "bad", "'bad' is not one of 'out', 'in', 'both'."),
            ],
        ),
        (
            "source",
            &[
                ("--max-lines", "0", "0 is not in the range 1<=x<=500."),
                ("--start-line", "0", "0 is not in the range x>=1."),
                ("--format", "bad", "'bad' is not one of 'json', 'text'."),
            ],
        ),
    ];
    for (command, options) in commands {
        check_option_order(command, options);
    }
}
fn check_option_order(command: &str, options: &[InvalidOption<'_>]) {
    for (name, value, message) in options {
        let expected = format!("Invalid value for '{name}': {message}");
        usage_error(&["graph", command, name, value], &expected);
        check_competing_options(command, (name, value, &expected), options);
    }
}
fn check_competing_options(command: &str, first: InvalidOption<'_>, options: &[InvalidOption<'_>]) {
    for (other, bad, _) in options.iter().filter(|option| option.0 != first.0) {
        check_argument_counts(command, &[first.0, first.1, other, bad], first.2);
    }
}
fn check_argument_counts(command: &str, options: &[&str], expected: &str) {
    for positional in [vec![], vec!["key"], vec!["key", "target", "extra"]] {
        let mut args = vec!["graph", command];
        args.extend(positional);
        args.extend(options);
        usage_error(&args, expected);
    }
}

#[test]
fn repeated_options_keep_first_position_but_use_last_value() {
    usage_error(
        &["graph", "context", "--depth", "2", "--direction", "bad", "--depth=-1"],
        "Invalid value for '--depth': -1 is not in the range 0<=x<=20.",
    );
    usage_error(
        &["graph", "context", "--depth", "-1", "--direction", "bad", "--depth=2"],
        "Invalid value for '--direction': 'bad' is not one of 'out', 'in', 'both'.",
    );
    usage_error(&["graph", "find", "--limit", "0", "--limit=1"], "Missing argument 'QUERY'.");
}

#[test]
fn syntax_errors_precede_eager_help_which_precedes_validation() {
    usage_error(&["graph", "find", "--limit", "0", "--help", "--bogus"], "No such option '--bogus'.");
    usage_error(&["graph", "find", "--limit", "0", "--help", "--limit"], "Option '--limit' requires an argument.");
    for args in [vec!["graph", "find", "--limit", "0", "--help"], vec!["report", "extra", "--format", "bad", "--help"]]
    {
        let output = invoke(&args);
        assert!(output.status.success());
        assert!(output.stderr.is_empty());
    }
    for command in ["report", "check"] {
        usage_error(
            &[command, "extra", "--format", "bad"],
            "Invalid value for '--format': 'bad' is not one of 'markdown', 'json'.",
        );
    }
}

#[test]
fn error_values_use_python_repr() {
    for (value, representation) in
        [("a'b", "\"a'b\""), ("a\nb", "'a\\nb'"), ("a'\"b\\", "'a\\'\"b\\\\'"), ("\u{1c}", "'\\x1c'")]
    {
        check_format_quoting(value, representation);
        usage_error(&[value], &format!("No such command {representation}."));
    }
    for (option, representation) in [("--a'b", "\"--a'b\""), ("--\n", "'--\\n'"), ("-'", "\"-'\""), ("-\n", "'-\\n'")] {
        let suggestion = if option == "--\n" { " Did you mean '--f'?" } else { "" };
        usage_error(&["report", option], &format!("No such option {representation}.{suggestion}"));
    }
}

fn check_format_quoting(value: &str, representation: &str) {
    for command in ["report", "check"] {
        usage_error(
            &[command, "--format", value],
            &format!("Invalid value for '--format': {representation} is not one of 'markdown', 'json'."),
        );
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
