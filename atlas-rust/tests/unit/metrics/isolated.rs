//! Core metrics contracts use in-memory records and JSON, not repositories or storage.
use super::*;

#[test]
fn config_validation_rejects_coercion_without_reading_a_project() {
    for value in [json!(-1), json!(true), json!("2"), json!(2.5)] {
        assert!(validate_config(&json!({"maxFileLines": value})).is_err(), "{value}");
    }
    assert!(validate_project_config(&json!({"mutations": {"rules": ["unknown"]}})).is_err());
    assert!(validate_project_config(&json!({"unexpected": 1})).is_err());
}

#[test]
fn files_without_callables_skip_grammar_loading() {
    // An unsupported grammar makes an unnecessary parse fail instead of silently slowing this path.
    let mut file = file("data.unknown", "not-a-grammar", b"not syntax");
    callable_metrics(&mut file).unwrap();
    let mut symbol = parsed_symbol(parse("python", b"class Brew: pass").root_node(), "class");
    symbol.line_count = Some(42);
    file.symbols.push(symbol.clone());
    callable_metrics(&mut file).unwrap();
    assert_eq!(serde_json::to_value(&file.symbols).unwrap(), json!([symbol]));
    assert_eq!(file.source.source, b"not syntax");
}

#[test]
fn dependency_metrics_ignore_unknown_endpoints_and_keep_isolated_nodes() {
    let view = json!({"nodes": ["a", "b", "isolated"], "edges": [
        edge("a", "b", "DEPENDS_ON"),
        edge("a", "missing", "DEPENDS_ON"),
        edge("missing", "b", "DEPENDS_ON"),
        edge("a", "a", "DEPENDS_ON")
    ]});
    let metrics = dependency_metrics(&view);
    assert_eq!(metrics.len(), 3);
    assert_eq!(metrics["a"], json!({"fanIn": 0, "fanOut": 1, "transitiveChangeImpact": 0, "instability": 1.0}));
    assert_eq!(metrics["b"], json!({"fanIn": 1, "fanOut": 0, "transitiveChangeImpact": 1, "instability": 0.0}));
    assert_eq!(metrics["isolated"], json!({"fanIn": 0, "fanOut": 0, "transitiveChangeImpact": 0, "instability": null}));
}
