use super::{NavigationReader, ProjectSelector, artifact, database, navigation_reader, run};
use crate::domain::repositories::{GraphDto, RepositoryError, RepositoryProtocol};
use sea_orm::{ConnectionTrait, DbBackend, Statement};
use serde_json::{Value, json};

fn repeated_artifact(count: usize) -> Value {
    let mut nodes = vec![json!({"stableKey": "file", "type": "file", "kind": "file", "level": "file",
        "name": "sample.py", "path": "sample.py", "properties": {"bytes": 123, "sha256": "abc"}})];
    nodes.extend((0..count).map(|i| {
        json!({"stableKey": format!("symbol:{i}"), "parentStableKey": "file",
        "type": "function", "kind": "function", "level": "callable", "name": format!("f{i}"),
        "path": "sample.py", "startLine": i + 1, "endLine": i + 2,
        "properties": {"decorators": ["one", "two"], "lineCount": 2, "parameterCount": 0,
            "cyclomaticComplexity": 1}})
    }));
    json!({"nodes": nodes,
        "edges": (0..count).map(|i| json!({"sourceStableKey": format!("symbol:{i}"),
            "targetStableKey": "file", "type": "CALLS", "confidence": "SYNTACTIC"})).collect::<Vec<_>>(),
        "diagnostics": (0..count).map(|i| json!({"severity": "warning", "path": "sample.py",
            "language": "python", "message": format!("warning {i}")})).collect::<Vec<_>>(),
        "mutationCandidates": (0..count).map(|i| json!({"id": format!("candidate:{i}"),
            "path": "sample.py", "language": "python", "sourceHash": "abc", "kind": "binary",
            "operator": null, "extra": [i, false]})).collect::<Vec<_>>()})
}

fn add_symbol_details(i: usize, node: &mut Value) {
    node["kind"] = json!("method");
    node["language"] = json!("python");
    node["qualifiedName"] = json!(format!("sample.f{i}"));
    node["startColumn"] = json!(i + 3);
    node["endColumn"] = json!(i + 4);
    node["signature"] = if i.is_multiple_of(2) { json!(format!("f{i}()")) } else { Value::Null };
    node["properties"]["visibility"] = json!("public");
    for (offset, &name) in super::super::graph_records::METRIC_NAMES.iter().enumerate() {
        node["properties"][name] = json!(i + offset);
    }
}

fn detailed_artifact() -> Value {
    let mut payload = repeated_artifact(40);
    for (i, node) in payload["nodes"].as_array_mut().unwrap().iter_mut().enumerate().skip(1) {
        add_symbol_details(i, node);
    }
    for (i, edge) in payload["edges"].as_array_mut().unwrap().iter_mut().enumerate() {
        edge["path"] = json!("sample.py");
        edge["evidence"] = if i.is_multiple_of(2) { json!("call") } else { Value::Null };
        edge["line"] = json!(i + 1);
        edge["typeOnly"] = json!(i.is_multiple_of(2));
    }
    payload
}

fn assert_symbol(detail: &Value, expected: &Value) {
    for field in [
        "stableKey",
        "parentStableKey",
        "type",
        "kind",
        "level",
        "name",
        "language",
        "qualifiedName",
        "path",
        "startLine",
        "startColumn",
        "endLine",
        "endColumn",
        "signature",
    ] {
        assert_eq!(detail[field], expected[field], "{field}");
    }
    for field in ["decorators", "visibility"] {
        assert_eq!(detail[field], expected["properties"][field], "{field}");
    }
    for field in super::super::graph_records::METRIC_NAMES {
        assert_eq!(detail["metrics"][field], expected["properties"][field], "{field}");
    }
}

#[test]
fn repeated_writes_preserve_values_order_and_nulls() {
    let (_temp, db, mut store) = database();
    let payload = detailed_artifact();
    let saved = store.save_new("Many", "/many", &payload).unwrap();
    assert_eq!(saved.stats.nodes, 41);
    assert_eq!(saved.stats.files, 1);
    assert_eq!(saved.stats.symbols, 40);
    assert_eq!(saved.stats.edges, 40);
    let facts = store.report_facts(&saved.repository_id).unwrap().unwrap();
    assert_eq!(facts["mutationCandidates"], payload["mutationCandidates"]);
    assert_eq!(facts["diagnostics"], payload["diagnostics"]);
    assert_eq!(facts["edges"], payload["edges"]);
    let mut reader = navigation_reader(ProjectSelector::Name("Many"), None, Some(&db)).unwrap();
    assert_eq!(reader.node("file").unwrap()["file"], json!({"bytes": 123, "sha256": "abc"}));
    for i in 0..40 {
        let expected = &payload["nodes"][i + 1];
        assert_eq!(facts["nodes"][i + 1]["stableKey"], expected["stableKey"]);
        let detail = reader.node(&format!("symbol:{i}")).unwrap();
        assert_symbol(&detail, expected);
    }
    let replacement = store.save(&saved.repository_id, &payload).unwrap();
    assert_ne!(replacement.graph_revision, saved.graph_revision);
    let mut expected = facts;
    expected["graphRevision"] = json!(replacement.graph_revision);
    assert_eq!(store.report_facts(&saved.repository_id).unwrap().unwrap(), expected);
}

#[test]
fn mutation_candidate_columns_preserve_values_and_file_mapping() {
    let (_temp, _, mut store) = database();
    let mut payload = repeated_artifact(0);
    payload["nodes"].as_array_mut().unwrap().push(json!({
        "stableKey": "other-file", "type": "file", "kind": "file", "level": "file",
        "name": "other.rs", "path": "other.rs", "properties": {}
    }));
    payload["mutationCandidates"] = json!([
        {"id": "candidate:z", "path": "other.rs", "language": "rust", "sourceHash": "rust-hash",
         "kind": "unary", "operator": "!", "extra": [1, true]},
        {"id": "candidate:a", "path": "sample.py", "language": "python", "sourceHash": "python-hash",
         "kind": "binary", "operator": null, "extra": [0, false]}
    ]);
    let saved = store.save_new("Candidates", "/candidates", &payload).unwrap();
    let rows = run(store.connection.query_all(Statement::from_string(
        DbBackend::Sqlite,
        "SELECT repository_id, candidate_id, file_key, ordinal, path, language, source_hash, \
         kind, operator, payload FROM graph_mutation_candidates ORDER BY ordinal",
    )))
    .unwrap();
    assert_eq!(rows.len(), 2);
    for (ordinal, (row, file_key)) in rows.iter().zip(["other-file", "file"]).enumerate() {
        let expected = &payload["mutationCandidates"][ordinal];
        assert_eq!(row.try_get::<String>("", "repository_id").unwrap(), saved.repository_id);
        assert_eq!(row.try_get::<String>("", "file_key").unwrap(), file_key);
        assert_eq!(row.try_get::<i64>("", "ordinal").unwrap(), ordinal as i64);
        assert_candidate_strings(row, expected);
        assert_eq!(row.try_get::<Option<String>>("", "operator").unwrap().as_deref(), expected["operator"].as_str());
        let stored_payload: String = row.try_get("", "payload").unwrap();
        assert_eq!(serde_json::from_str::<Value>(&stored_payload).unwrap(), *expected);
    }
}

fn assert_candidate_strings(row: &sea_orm::QueryResult, expected: &Value) {
    for (column, field) in [
        ("candidate_id", "id"),
        ("path", "path"),
        ("language", "language"),
        ("source_hash", "sourceHash"),
        ("kind", "kind"),
    ] {
        assert_eq!(row.try_get::<String>("", column).unwrap(), expected[field].as_str().unwrap(), "{column}");
    }
}

#[test]
fn late_write_errors_roll_back_replacement_and_registration() {
    let (temp, _, mut store) = database();
    let original = artifact(temp.path());
    let saved = store.save_new("Original", "/original", &original).unwrap();
    let facts = store.report_facts(&saved.repository_id).unwrap().unwrap();
    run(store.connection.execute_unprepared(
        "CREATE TRIGGER reject_diagnostic BEFORE INSERT ON graph_diagnostics \
         WHEN NEW.message = 'warning 19' BEGIN SELECT RAISE(ABORT, 'diagnostic rejected'); END; \
         CREATE TRIGGER ignore_diagnostic BEFORE INSERT ON graph_diagnostics \
         WHEN NEW.message = 'ignored' BEGIN SELECT RAISE(IGNORE); END;",
    ))
    .unwrap();
    let mut duplicate = repeated_artifact(20);
    duplicate["mutationCandidates"][19]["id"] = json!("candidate:0");
    let mut missing = repeated_artifact(20);
    missing["edges"][19]["targetStableKey"] = json!("missing");
    let mut ignored = repeated_artifact(20);
    ignored["diagnostics"][19]["message"] = json!("ignored");
    for (payload, message) in [
        (duplicate, "UNIQUE constraint failed"),
        (ignored, "None of the records are inserted"),
        (repeated_artifact(20), "diagnostic rejected"),
        (missing, "FOREIGN KEY constraint failed"),
    ] {
        assert_write_error(store.save(&saved.repository_id, &payload), message);
        assert_write_error(store.save_new("Rejected", "/rejected", &payload), message);
        assert_eq!(store.graph(&saved.repository_id).unwrap().unwrap().graph_revision, saved.graph_revision);
        assert_eq!(store.report_facts(&saved.repository_id).unwrap().unwrap(), facts);
        assert_eq!(store.list().unwrap().len(), 1);
    }
}

fn assert_write_error(result: anyhow::Result<GraphDto>, message: &str) {
    let error = result.unwrap_err();
    assert!(error.to_string().contains(message), "{error}");
    assert_eq!(error.downcast_ref::<RepositoryError>().unwrap().status, 500);
}

#[test]
#[ignore = "manual persistence timing; run with --ignored --nocapture --test-threads=1"]
fn indexing_write_timing() {
    let (_temp, _, mut store) = database();
    let payload = repeated_artifact(2000);
    let saved = store.save_new("Timing", "/timing", &payload).unwrap();
    for _ in 0..7 {
        let start = std::time::Instant::now();
        let result = store.save(&saved.repository_id, &payload).unwrap();
        eprintln!("save 2001 nodes / 16002 graph rows: {:?}", start.elapsed());
        assert_eq!(result.stats.nodes, 2001);
        assert_eq!(result.stats.edges, 2000);
    }
}
