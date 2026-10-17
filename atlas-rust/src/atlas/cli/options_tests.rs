use super::options::{Options, json_dump};
use serde_json::json;

#[test]
fn folder_aliases_attached_values_and_literal_arguments() {
    for option in ["-f", "--f", "--folder"] {
        let args = [option.into(), "folder".into()];
        assert_eq!(Options::parse("index", &args, (&["--folder"], &[])).unwrap().get("--folder", "."), "folder");
        let missing = Options::parse("index", &[option.into()], (&["--folder"], &[])).err().unwrap();
        assert_eq!(missing.to_string(), format!("Option '{option}' requires an argument."));
    }
    assert_eq!(
        Options::parse("index", &["-ffolder".into()], (&["--folder"], &[])).unwrap().get("--folder", "."),
        "folder"
    );
    let literal = Options::parse("graph show", &["--".into(), "--help".into()], (&[], &[])).unwrap();
    assert_eq!(literal.positional, vec!["--help"]);
    let attached =
        Options::parse("report", &["-f/tmp/project".into(), "--format=json".into()], (&["--folder", "--format"], &[]))
            .unwrap();
    assert_eq!(attached.get("--folder", "."), "/tmp/project");
    assert_eq!(attached.get("--format", "markdown"), "json");
}
#[test]
fn help_tokens_used_as_values_do_not_request_help() {
    let folder = Options::parse("report", &["--folder".into(), "--help".into()], (&["--folder"], &["--help"])).unwrap();
    assert_eq!(folder.get("--folder", "."), "--help");
    assert!(!folder.has("--help"));
    let format = Options::parse("report", &["--format".into(), "--help".into()], (&["--format"], &["--help"])).unwrap();
    assert!(!format.has("--help"));
    assert!(format.choice("--format", "markdown", &["markdown", "json"]).is_err());
}
#[test]
fn graph_help_respects_literal_option_like_queries() {
    use super::graph_options::{GraphOptions, Operation};
    let options = GraphOptions::parse("find", &["--".into(), "--help".into()]).unwrap().unwrap();
    assert!(matches!(options.operation, Operation::Find(query, 10) if query == "--help"));
    assert!(GraphOptions::parse("find", &["--help".into()]).unwrap().is_none());
    let options =
        GraphOptions::parse("find", &["--limit".into(), "1".into(), "--".into(), "--help".into()]).unwrap().unwrap();
    assert!(matches!(options.operation, Operation::Find(query, 1) if query == "--help"));
}
#[test]
fn unknown_short_option_clusters_report_the_first_flag() {
    for command in ["", "projects", "report", "graph", "graph find"] {
        let arguments = ["-hfok".into()];
        assert_eq!(
            Options::parse(command, &arguments, (&["--folder"], &["--help"])).err().unwrap().to_string(),
            "No such option '-h'."
        );
        assert_eq!(
            Options::parse_group(command, &["-hh".into()], (&[], &["--help"])).err().unwrap().to_string(),
            "No such option '-h'."
        );
    }
}
#[test]
fn root_and_graph_group_terminators_leave_subcommands_unparsed() {
    let root = ["--".into(), "projects".into()];
    let (options, tail) = Options::parse_group("", &root, (&[], &["--help"])).unwrap();
    assert!(!options.has("--help"));
    assert_eq!(tail, &["projects"]);
    let graph = ["--project".into(), "coffee".into(), "--".into(), "overview".into()];
    let (options, tail) = Options::parse_group("graph", &graph, (&["--project"], &["--help"])).unwrap();
    assert_eq!(options.get("--project", ""), "coffee");
    assert_eq!(tail, &["overview"]);
}
#[test]
fn graph_numeric_bounds_and_choice_errors() {
    let args = ["--limit".into(), "many".into(), "--format".into(), "JSON".into()];
    let options = Options::parse("graph find", &args, (&["--limit", "--format"], &[])).unwrap();
    assert_eq!(
        options.number("--limit", 10, (1, 100)).unwrap_err().to_string(),
        "Invalid value for '--limit': 'many' is not a valid integer range."
    );
    assert_eq!(
        options.choice("--format", "json", &["json", "text"]).unwrap_err().to_string(),
        "Invalid value for '--format': 'JSON' is not one of 'json', 'text'."
    );
}
#[test]
fn compact_json_uses_python_spaces_without_changing_strings() {
    let value = json!({"quoted": "\"a,b:c\\\"", "values": [1, true, null, "café"]});
    assert_eq!(serde_json::from_str::<serde_json::Value>(&json_dump(&value)).unwrap(), value);
    assert!(json_dump(&value).contains("[1, true, null, \"café\"]"));
}
