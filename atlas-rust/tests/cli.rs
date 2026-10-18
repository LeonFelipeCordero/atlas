//! Exercise clap through the real binary without touching the caller's database.
#[path = "support/cli.rs"]
mod cli_support;
use cli_support::invoke;

#[test]
fn all_commands_offer_generated_help_without_side_effects() {
    for path in [
        "",
        "index",
        "projects",
        "report",
        "check",
        "mutations",
        "graph",
        "graph overview",
        "graph find",
        "graph show",
        "graph children",
        "graph context",
        "graph path",
        "graph source",
    ] {
        let mut args: Vec<_> = path.split_whitespace().collect();
        args.push("--help");
        let result = invoke(&args);
        assert_eq!(result.status.code(), Some(0), "{path}");
        assert!(result.stderr.is_empty(), "{path}");
        let help = String::from_utf8(result.stdout).unwrap();
        assert!(help.contains("Usage:"), "{path}: {help}");
        assert!(help.contains("--help"), "{path}: {help}");
    }
}

#[test]
fn syntax_errors_exit_two_before_opening_a_database() {
    for args in [
        vec![],
        vec!["graph"],
        vec!["unknown"],
        vec!["index", "--folder"],
        vec!["projects", "extra"],
        vec!["check", "--format", "xml"],
        vec!["graph", "show"],
        vec!["graph", "path", "from"],
        vec!["graph", "find", "brew", "--limit", "0"],
        vec!["graph", "context", "brew", "--relations", "INVALID"],
        vec!["graph", "source", "brew", "--max-lines", "501"],
    ] {
        let result = invoke(&args);
        assert_eq!(result.status.code(), Some(2), "{args:?}");
        assert!(result.stdout.is_empty(), "{args:?}");
        assert!(!result.stderr.is_empty(), "{args:?}");
    }
}

#[test]
fn rules_bypass_the_filesystem_and_database() {
    let output = invoke(&["mutations", "--folder", "/does-not-exist", "--rules", "--saved"]);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let payload: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(payload["rules"].is_array());
}
