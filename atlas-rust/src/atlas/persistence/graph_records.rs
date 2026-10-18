use super::models::*;
use anyhow::{Result, anyhow, ensure};
use sea_orm::{ConnectionTrait, EntityTrait, IntoActiveModel};
use serde_json::Value;
use std::collections::{HashMap, HashSet};

pub use super::graph_validation::{METRIC_NAMES, collection};
pub const POSITIONS: [&str; 4] = ["startLine", "startColumn", "endLine", "endColumn"];
pub fn text(value: &Value, name: &str) -> Option<String> {
    value[name].as_str().map(str::to_owned)
}
pub fn required(value: &Value, name: &str) -> Result<String> {
    text(value, name).ok_or_else(|| anyhow!("Missing or invalid graph field: {name}"))
}
pub fn is_symbol(node: &Value) -> bool {
    let level = node["level"].as_str().unwrap_or("");
    matches!(level, "type" | "callable" | "symbol")
        || level == "module" && !matches!(node["kind"].as_str(), Some("directory" | "folder"))
        || node.get("signature").is_some()
        || POSITIONS.iter().any(|name| node.get(name).is_some())
        || node["properties"].get("visibility").is_some()
        || node["properties"].get("decorators").is_some()
}
pub fn validate_parentage(artifact: &Value) -> Result<()> {
    super::graph_validation::validate_artifact(artifact)?;
    let mut parents = HashMap::new();
    for node in collection(artifact, "nodes") {
        parents.insert(required(node, "stableKey")?, text(node, "parentStableKey"));
    }
    let mut complete = HashSet::new();
    for key in parents.keys() {
        validate_chain(key, &parents, &mut complete)?;
    }
    Ok(())
}
fn validate_chain(key: &str, parents: &HashMap<String, Option<String>>, complete: &mut HashSet<String>) -> Result<()> {
    let mut chain = HashSet::new();
    let mut current = Some(key);
    while let Some(key) = current.filter(|k| parents.contains_key(*k) && !complete.contains(*k)) {
        ensure!(chain.insert(key.to_owned()), "Graph node has cyclic parentage: {key}");
        current = parents[key].as_deref();
    }
    complete.extend(chain);
    Ok(())
}
pub fn node_record(id: &str, ordinal: usize, n: &Value) -> Result<GraphNodeRow> {
    Ok(GraphNodeRow {
        repository_id: id.into(),
        node_key: required(n, "stableKey")?,
        parent_key: text(n, "parentStableKey"),
        ordinal: ordinal as i64,
        type_: required(n, "type")?,
        kind: required(n, "kind")?,
        level: required(n, "level")?,
        name: required(n, "name")?,
        language: text(n, "language"),
        qualified_name: text(n, "qualifiedName"),
        path: text(n, "path"),
    })
}
fn symbol_record(id: &str, key: &str, n: &Value) -> GraphSymbolRow {
    GraphSymbolRow {
        repository_id: id.into(),
        node_key: key.into(),
        start_line: n["startLine"].as_i64(),
        start_column: n["startColumn"].as_i64(),
        end_line: n["endLine"].as_i64(),
        end_column: n["endColumn"].as_i64(),
        signature: text(n, "signature"),
        visibility: text(&n["properties"], "visibility"),
    }
}
fn metric_record(id: &str, key: &str, n: &Value) -> GraphNodeMetricRow {
    let p = &n["properties"];
    GraphNodeMetricRow {
        repository_id: id.into(),
        node_key: key.into(),
        line_count: p["lineCount"].as_i64(),
        parameter_count: p["parameterCount"].as_i64(),
        base_complexity: p["baseCyclomaticComplexity"].as_i64(),
        nested_complexity: p["nestedCyclomaticComplexity"].as_i64(),
        loop_complexity: p["loopNestedComplexity"].as_i64(),
        total_complexity: p["cyclomaticComplexity"].as_i64(),
        max_decision_depth: p["maxDecisionDepth"].as_i64(),
    }
}
pub async fn insert_node_details(connection: &impl ConnectionTrait, id: &str, n: &Value) -> Result<()> {
    let key = required(n, "stableKey")?;
    if n["level"] == "file" {
        let row = GraphFileRow {
            repository_id: id.into(),
            node_key: key.clone(),
            byte_count: n["properties"]["bytes"].as_i64(),
            sha256: text(&n["properties"], "sha256"),
        };
        graph_files::Entity::insert(row.into_active_model()).exec(connection).await?;
    }
    if is_symbol(n) {
        graph_symbols::Entity::insert(symbol_record(id, &key, n).into_active_model()).exec(connection).await?;
        for (ordinal, decorator) in collection(&n["properties"], "decorators").iter().enumerate() {
            let row = GraphNodeDecoratorRow {
                repository_id: id.into(),
                node_key: key.clone(),
                ordinal: ordinal as i64,
                decorator: decorator.as_str().ok_or_else(|| anyhow!("Graph decorators must contain strings"))?.into(),
            };
            graph_node_decorators::Entity::insert(row.into_active_model()).exec(connection).await?;
        }
    }
    if METRIC_NAMES.iter().any(|name| n["properties"].get(name).is_some()) {
        graph_node_metrics::Entity::insert(metric_record(id, &key, n).into_active_model()).exec(connection).await?;
    }
    Ok(())
}
pub async fn insert_edges(connection: &impl ConnectionTrait, id: &str, artifact: &Value) -> Result<()> {
    for (ordinal, e) in collection(artifact, "edges").iter().enumerate() {
        let row = GraphEdgeRow {
            repository_id: id.into(),
            ordinal: ordinal as i64,
            source_key: required(e, "sourceStableKey")?,
            target_key: required(e, "targetStableKey")?,
            relationship: required(e, "type")?,
            confidence: required(e, "confidence")?,
            path: text(e, "path"),
            evidence: text(e, "evidence"),
            line: e["line"].as_i64(),
            type_only: e["typeOnly"] == true,
        };
        graph_edges::Entity::insert(row.into_active_model()).exec(connection).await?;
    }
    Ok(())
}
pub async fn insert_diagnostics(connection: &impl ConnectionTrait, id: &str, artifact: &Value) -> Result<()> {
    for (ordinal, d) in collection(artifact, "diagnostics").iter().enumerate() {
        let row = GraphDiagnosticRow {
            repository_id: id.into(),
            ordinal: ordinal as i64,
            severity: required(d, "severity")?,
            path: required(d, "path")?,
            language: required(d, "language")?,
            message: required(d, "message")?,
        };
        graph_diagnostics::Entity::insert(row.into_active_model()).exec(connection).await?;
    }
    Ok(())
}
pub async fn insert_candidates(connection: &impl ConnectionTrait, id: &str, artifact: &Value) -> Result<()> {
    let files: HashMap<_, _> = collection(artifact, "nodes")
        .iter()
        .filter(|n| n["level"] == "file")
        .map(|n| Ok((required(n, "path")?, required(n, "stableKey")?)))
        .collect::<Result<_>>()?;
    for (ordinal, c) in collection(artifact, "mutationCandidates").iter().enumerate() {
        let path = required(c, "path")?;
        let row = GraphMutationCandidateRow {
            repository_id: id.into(),
            candidate_id: required(c, "id")?,
            file_key: files.get(&path).ok_or_else(|| anyhow!("Candidate file not found: {path}"))?.clone(),
            ordinal: ordinal as i64,
            path,
            language: required(c, "language")?,
            source_hash: required(c, "sourceHash")?,
            kind: required(c, "kind")?,
            operator: text(c, "operator"),
            payload: serde_json::to_string(c)?,
        };
        graph_mutation_candidates::Entity::insert(row.into_active_model()).exec(connection).await?;
    }
    Ok(())
}
