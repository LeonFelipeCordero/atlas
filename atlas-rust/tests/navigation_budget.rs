//! Traversal budgets count unseen edges, not previously visited adjacency rows.
use atlas::{
    bootstrap::{migrate_database, navigation_service, repository_service},
    domain::navigation::{PathRequest, TraversalRequest},
    indexer::analyze_repository,
};
use serde_json::json;
use std::fs;

#[test]
fn repeated_calls_use_exact_budget_and_report_real_truncation() -> anyhow::Result<()> {
    let workspace = tempfile::tempdir()?;
    let root = workspace.path().join("repo");
    fs::create_dir(&root)?;
    fs::write(
        root.join("main.py"),
        "def a():\n    b()\n    b()\n    b()\n    c()\n\ndef b():\n    d()\n\ndef c():\n    pass\n\ndef d():\n    pass\n",
    )?;
    let graph = analyze_repository(&root)?;
    let key = |name: &str| {
        graph["nodes"].as_array().unwrap().iter()
        .find(|n| n["name"] == name && n["kind"] == "function")
        .unwrap()["stableKey"].as_str().unwrap().to_owned()
    };
    let (a, b, d) = (key("a"), key("b"), key("d"));
    let database = workspace.path().join("atlas.sqlite");
    migrate_database(Some(&database))?;
    let saved = repository_service(Some(&database))?.save_folder(&root, &graph)?;
    let mut service = navigation_service(Some(&saved.repository_id), None, Some(&database))?;
    let request = TraversalRequest {
        key: a.clone(),
        direction: "both".into(),
        relations: vec!["CALLS".into()],
        depth: 8,
        max_nodes: 4,
        max_edges: 5,
    };
    let result = service.path(&PathRequest { target: d.clone(), traversal: request.clone() })?;
    assert_eq!(result["status"], "found");
    assert_eq!(result["path"], json!([a, b, d]));
    assert_eq!(result["edges"].as_array().unwrap().len(), 5);
    assert_eq!(result["truncated"], false);
    assert_eq!(result["boundaries"], json!([]));

    let result = service
        .path(&PathRequest { target: d.clone(), traversal: TraversalRequest { max_edges: 4, ..request.clone() } })?;
    assert_eq!(result["status"], "unknown");
    assert_eq!(result["edges"].as_array().unwrap().len(), 4);
    assert_eq!(result["truncated"], true);
    assert!(result["boundaries"].as_array().unwrap().iter().any(|b| b["reason"] == "maxEdges"));

    let result = service.path(&PathRequest { target: d, traversal: TraversalRequest { max_nodes: 3, ..request } })?;
    assert_eq!(result["status"], "unknown");
    assert_eq!(result["nodes"].as_array().unwrap().len(), 3);
    assert!(result["boundaries"].as_array().unwrap().iter().any(|b| b["reason"] == "maxNodes"));
    Ok(())
}
