use super::{
    database::migrate_database,
    navigation::{ProjectSelector, navigation_reader},
    repositories::repository_store,
};
use crate::{
    domain::{
        navigation::{PathRequest, TraversalRequest},
        repositories::RepositoryProtocol,
    },
    services::{
        navigation::NavigationService,
        navigation_source::{local_bytes, source_lines, verified_excerpt},
    },
};
use diesel::connection::SimpleConnection;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::path::Path;

fn artifact(root: &Path) -> Value {
    let bytes = b"def brew():\n    return 1\n";
    std::fs::write(root.join("coffee.py"), bytes).unwrap();
    json!({"schemaVersion": 2, "repository": {"name": "coffee", "path": root, "indexedAt": "2026-01-01T00:00:00Z"},
        "nodes": [
            {"stableKey": "file:coffee.py", "type": "file", "kind": "file", "level": "file", "name": "coffee.py", "path": "coffee.py", "properties": {"bytes": bytes.len(), "sha256": format!("{:x}", Sha256::digest(bytes)), "lineCount": 2}},
            {"stableKey": "brew", "parentStableKey": "file:coffee.py", "type": "function", "kind": "function", "level": "callable", "name": "brew", "path": "coffee.py", "startLine": 1, "endLine": 2, "properties": {"decorators": ["one", "two"], "parameterCount": 0, "cyclomaticComplexity": 1}},
            {"stableKey": "external:serve", "type": "external", "kind": "external", "level": "external", "name": "serve"}
        ], "edges": [{"sourceStableKey": "brew", "targetStableKey": "external:serve", "type": "CALLS", "confidence": "SYNTACTIC", "path": "coffee.py", "line": 1}],
        "diagnostics": [{"severity": "warning", "path": "coffee.py", "language": "python", "message": "one"}],
        "mutationCandidates": [{"id": "candidate", "path": "coffee.py", "language": "python", "sourceHash": "abc", "kind": "binary", "operator": null, "extra": [0, false]}]})
}
#[test]
fn roundtrip_normalized_rows_and_transaction_replacement() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    migrate_database(Some(&db)).unwrap();
    let payload = artifact(temp.path());
    let mut store = repository_store(Some(&db)).unwrap();
    let saved = store.save_new("Coffee", &temp.path().to_string_lossy(), &payload).unwrap();
    assert_eq!(saved.stats.files, 1);
    assert_eq!(saved.stats.symbols, 1);
    assert_eq!(saved.stats.edges, 1);
    assert_eq!(store.resolve("COFFEE").unwrap(), Some(saved.repository_id.clone()));
    assert!(store.register("coffee", "/different").is_err());
    let facts = store.report_facts(&saved.repository_id).unwrap().unwrap();
    assert_eq!(facts["mutationCandidates"], payload["mutationCandidates"]);
    assert_eq!(facts["nodes"][1]["parameterCount"], 0);
    let mut broken = payload.clone();
    broken["nodes"][1]["parentStableKey"] = json!("missing");
    assert!(store.save(&saved.repository_id, &broken).is_err());
    let current = store.graph(&saved.repository_id).unwrap().unwrap();
    assert_eq!(current.graph_revision, saved.graph_revision);
    assert_eq!(store.report_facts(&saved.repository_id).unwrap().unwrap(), facts);
    let empty = json!({"nodes": [], "edges": [], "diagnostics": [], "mutationCandidates": []});
    let replacement = store.save(&saved.repository_id, &empty).unwrap();
    assert_ne!(replacement.graph_revision, saved.graph_revision);
    assert_eq!(replacement.stats.nodes, 0);
    let facts = store.report_facts(&saved.repository_id).unwrap().unwrap();
    for name in ["nodes", "edges", "diagnostics", "mutationCandidates"] {
        assert_eq!(facts[name], json!([]));
    }
}
#[test]
fn invalid_artifact_roots_preserve_the_saved_graph() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let saved = store.save_new("Coffee", &temp.path().to_string_lossy(), &artifact(temp.path())).unwrap();
    let before = store.report_facts(&saved.repository_id).unwrap().unwrap();
    for invalid in [Value::Null, json!([]), json!(42), json!("not an object"), json!(true)] {
        assert!(store.save(&saved.repository_id, &invalid).is_err());
        assert!(store.save_new("Invalid", "/invalid", &invalid).is_err());
        assert_eq!(store.graph(&saved.repository_id).unwrap().unwrap().graph_revision, saved.graph_revision);
        assert_eq!(store.report_facts(&saved.repository_id).unwrap().unwrap(), before);
        assert_eq!(store.list().unwrap().len(), 1);
    }
}
#[test]
fn malformed_record_mappings_and_fields_preserve_saved_rows() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let original = artifact(temp.path());
    let saved = store.save_new("Coffee", &temp.path().to_string_lossy(), &original).unwrap();
    let before = store.report_facts(&saved.repository_id).unwrap().unwrap();
    for (pointer, value) in invalid_record_shapes() {
        let mut invalid = original.clone();
        *invalid.pointer_mut(pointer).unwrap() = value;
        assert!(store.save(&saved.repository_id, &invalid).is_err(), "{pointer}: {invalid}");
        assert!(store.save_new("Invalid", "/invalid", &invalid).is_err());
        assert_eq!(
            serde_json::to_value(store.graph(&saved.repository_id).unwrap().unwrap()).unwrap(),
            serde_json::to_value(&saved).unwrap()
        );
        assert_eq!(store.report_facts(&saved.repository_id).unwrap().unwrap(), before);
        assert_eq!(store.list().unwrap().len(), 1);
    }
}
fn invalid_record_shapes() -> Vec<(&'static str, Value)> {
    let mappings = ["/repository", "/nodes/0/properties"];
    let records = ["/nodes/0", "/edges/0", "/diagnostics/0", "/mutationCandidates/0"];
    let fields = [
        "/repository/name",
        "/repository/path",
        "/repository/indexedAt",
        "/schemaVersion",
        "/nodes/0/path",
        "/nodes/0/properties/sha256",
        "/nodes/1/properties/parameterCount",
        "/edges/0/path",
        "/diagnostics/0/message",
        "/mutationCandidates/0/operator",
    ];
    let mut invalid: Vec<_> = mappings
        .into_iter()
        .flat_map(|pointer| {
            [json!(true), json!(42), json!("bad"), json!([1])].into_iter().map(move |value| (pointer, value))
        })
        .collect();
    invalid.extend(records.into_iter().flat_map(|pointer| {
        [Value::Null, json!(false), json!([]), json!("bad")].into_iter().map(move |value| (pointer, value))
    }));
    invalid.extend(
        fields.into_iter().flat_map(|pointer| [json!([]), json!({})].into_iter().map(move |value| (pointer, value))),
    );
    invalid
}
#[test]
fn metadata_scalar_conversions_and_falsey_mapping_defaults_match_python() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let saved = store
        .save_new(
            "Coffee",
            "/coffee",
            &json!({"schemaVersion": "2", "repository": {"name": 42, "path": true, "indexedAt": 2.5}}),
        )
        .unwrap();
    assert_eq!(saved.schema_version, Some(2));
    assert_eq!(saved.root_name.as_deref(), Some("42"));
    assert_eq!(saved.root_path.as_deref(), Some("1"));
    assert_eq!(saved.indexed_at.as_deref(), Some("2.5"));
    for value in [Value::Null, json!(false), json!(0), json!(""), json!([]), json!({})] {
        let mut payload = artifact(temp.path());
        payload["repository"] = value.clone();
        payload["nodes"][0]["properties"] = value;
        let saved = store.save(&saved.repository_id, &payload).unwrap();
        assert_eq!(saved.root_name, None);
    }
    let before = store.graph(&saved.repository_id).unwrap().unwrap().graph_revision;
    for value in [json!(1.5), json!("bad")] {
        assert!(store.save(&saved.repository_id, &json!({"schemaVersion": value})).is_err());
        assert_eq!(store.graph(&saved.repository_id).unwrap().unwrap().graph_revision, before);
    }
}
#[test]
fn nonexistent_database_paths_resolve_symlinks_before_parents() {
    use super::database::absolute_path;
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    std::fs::create_dir_all(root.join("actual/nested")).unwrap();
    std::os::unix::fs::symlink("actual/nested", root.join("link")).unwrap();
    let requested = root.join("link/../new.sqlite");
    assert_eq!(absolute_path(&requested).unwrap(), root.join("actual/new.sqlite"));
    migrate_database(Some(&requested)).unwrap();
    assert!(root.join("actual/new.sqlite").exists());
    assert!(!root.join("new.sqlite").exists());
    std::os::unix::fs::symlink("actual/missing/child", root.join("dangling")).unwrap();
    assert_eq!(absolute_path(&root.join("dangling/../new.sqlite")).unwrap(), root.join("actual/missing/new.sqlite"));
    std::os::unix::fs::symlink("loop", root.join("loop")).unwrap();
    assert!(absolute_path(&root.join("loop/file")).is_err());
    assert_eq!(local_bytes(root.join("loop").to_str().unwrap(), "file").0, "unsafe");
}
#[test]
fn malformed_graphs_and_new_registration_roll_back() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let payload = artifact(temp.path());
    for field in ["nodes", "edges", "diagnostics", "mutationCandidates"] {
        let mut broken = payload.clone();
        broken[field] = json!({});
        assert!(store.save_new("invalid", "/tmp", &broken).is_err());
        assert!(store.list().unwrap().is_empty());
    }
    let mut broken = payload.clone();
    broken["nodes"][0]["parentStableKey"] = json!("brew");
    assert!(store.save_new("invalid", "/tmp", &broken).unwrap_err().to_string().contains("cyclic parentage"));
    broken = payload.clone();
    broken["edges"][0]["targetStableKey"] = json!("missing");
    assert!(store.save_new("invalid", "/tmp", &broken).is_err());
    assert!(store.list().unwrap().is_empty());
}
#[test]
fn navigation_order_source_verification_and_revision_errors() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let saved = store.save_new("Coffee", &temp.path().to_string_lossy(), &artifact(temp.path())).unwrap();
    let reader = navigation_reader(ProjectSelector::Name("COFFEE"), Some(&saved.graph_revision), Some(&db)).unwrap();
    let mut service = NavigationService::new(reader);
    assert_eq!(service.find("coffee.py", 10).unwrap()["nodes"][0]["level"], "file");
    assert_eq!(service.children("file:coffee.py", 1, 0.into()).unwrap()["nextOffset"], Value::Null);
    let shown = service.show("brew").unwrap();
    assert_eq!(shown["node"]["decorators"], json!(["one", "two"]));
    assert_eq!(shown["ancestors"][0]["stableKey"], "file:coffee.py");
    let request = TraversalRequest {
        key: "brew".into(),
        direction: "out".into(),
        relations: vec!["CALLS".into()],
        depth: 2,
        max_nodes: 30,
        max_edges: 100,
    };
    let context = service.context(&request).unwrap();
    assert_eq!(context["truncated"], false);
    assert_eq!(context["boundaries"][0]["expandable"], false);
    let path = service.path(&PathRequest { target: "external:serve".into(), traversal: request }).unwrap();
    assert_eq!(path["status"], "found");
    assert_eq!(path["path"], json!(["brew", "external:serve"]));
    assert_eq!(service.source("brew", 1, None).unwrap()["source"]["nextStartLine"], 2);
    std::fs::write(temp.path().join("coffee.py"), "changed").unwrap();
    assert_eq!(service.source("brew", 80, None).unwrap()["source"]["status"], "changed");
    assert!(
        navigation_reader(ProjectSelector::Name("Coffee"), Some("stale"), Some(&db))
            .err()
            .unwrap()
            .to_string()
            .contains("Stale graph revision")
    );
    assert!(service.show("missing").unwrap_err().to_string().starts_with("Node not found: missing"));
}
#[test]
fn huge_source_start_lines_remain_exact_and_offsets_do_not_wrap() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    let saved = store.save_new("Coffee", &temp.path().to_string_lossy(), &artifact(temp.path())).unwrap();
    let reader = navigation_reader(ProjectSelector::Name("Coffee"), None, Some(&db)).unwrap();
    let mut service = NavigationService::new(reader);
    let decimal = "1234567890".repeat(50);
    let huge: serde_json::Number = decimal.parse().unwrap();
    let result = service.source("brew", 80, Some(huge.clone())).unwrap();
    assert_eq!(result["filters"]["startLine"], json!(huge));
    assert_eq!(result["source"]["startLine"], json!(huge));
    assert_eq!(result["source"]["endLine"], 2);
    assert_eq!(result["source"]["lines"], json!([]));
    assert_eq!(result["source"]["nextStartLine"], Value::Null);
    assert_eq!(result["source"]["truncated"], false);
    assert!(crate::cli::graph_source_output::source_text(&result).contains(&format!("\"startLine\": {decimal}")));
    assert!(
        service
            .children("file:coffee.py", 30, huge)
            .unwrap_err()
            .to_string()
            .contains("too large to convert to SQLite INTEGER")
    );
    let huge = (i64::MAX as u64 + 1).into();
    assert!(service.children("file:coffee.py", 30, huge).is_err());
    assert_eq!(store.graph(&saved.repository_id).unwrap().unwrap().graph_revision, saved.graph_revision);
}
#[test]
fn read_only_navigation_does_not_create_or_migrate() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("absent/db.sqlite");
    assert!(navigation_reader(ProjectSelector::Name("no"), None, Some(&db)).is_err());
    assert!(!db.exists());
    assert!(!db.parent().unwrap().exists());
    let db = temp.path().join("empty.sqlite");
    std::fs::write(&db, []).unwrap();
    assert!(
        navigation_reader(ProjectSelector::Name("no"), None, Some(&db))
            .err()
            .unwrap()
            .to_string()
            .contains("Missing graph schema/index")
    );
}
#[test]
fn migrations_upgrade_legacy_revision_without_backfilling() {
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    let mut connection = super::database::create_engine(Some(&db)).unwrap();
    connection.batch_execute(include_str!("migrations/versions/0001_initial.sql")).unwrap();
    connection.batch_execute("CREATE TABLE alembic_version(version_num VARCHAR(32) NOT NULL PRIMARY KEY); INSERT INTO alembic_version VALUES('0001_initial'); INSERT INTO repositories VALUES('id','old','/old',1); INSERT INTO repository_graphs VALUES('id','{}',2);").unwrap();
    drop(connection);
    migrate_database(Some(&db)).unwrap();
    let mut store = repository_store(Some(&db)).unwrap();
    assert!(store.graph("id").unwrap().is_none());
    assert_eq!(store.list().unwrap()[0].imported_at, None);
}
#[test]
fn migration_schema_sql_matches_python_exactly() {
    use diesel::{prelude::*, sql_types::Text};
    #[derive(QueryableByName)]
    struct SchemaSql {
        #[diesel(sql_type = Text)]
        name: String,
        #[diesel(sql_type = Text)]
        sql: String,
    }
    let temp = tempfile::tempdir().unwrap();
    let db = temp.path().join("db.sqlite");
    migrate_database(Some(&db)).unwrap();
    let mut connection = super::database::create_engine(Some(&db)).unwrap();
    let rows = diesel::sql_query("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name")
        .load::<SchemaSql>(&mut connection)
        .unwrap();
    let actual = json!(rows.into_iter().map(|r| vec![r.name, r.sql]).collect::<Vec<_>>());
    let expected: Value = serde_json::from_str(include_str!("migrations/schema.json")).unwrap();
    assert_eq!(actual, expected);
}
#[test]
fn source_limits_encoding_and_containment() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path().join("root");
    std::fs::create_dir(&root).unwrap();
    std::fs::write(root.join("good"), "a\r\nb\n").unwrap();
    assert_eq!(local_bytes(root.to_str().unwrap(), "../outside").0, "unsafe");
    assert_eq!(source_lines(b"a\rb\r\nc\n").unwrap(), vec!["a\rb", "c"]);
    assert!(source_lines(&[255]).is_err());
    let node = json!({"path": "good", "level": "file"});
    let options = crate::domain::navigation::SourceOptions { max_lines: 1, start_line: Some(2.into()) };
    assert_eq!(verified_excerpt(&node, b"a\r\nb\n", &options)["lines"], json!(["b"]));
    assert_eq!(verified_excerpt(&node, &[255], &options)["status"], "unsupported_encoding");
    std::os::unix::fs::symlink(temp.path(), root.join("escape")).unwrap();
    assert_eq!(local_bytes(root.to_str().unwrap(), "escape").0, "unsafe");
    std::os::unix::fs::symlink(temp.path().join("missing"), root.join("missing_escape")).unwrap();
    assert_eq!(local_bytes(root.to_str().unwrap(), "missing_escape").0, "unsafe");
}
