use super::{models::*, navigation_queries::*, schema::*};
use crate::domain::repositories::{GraphDto, GraphStatsDto};
use anyhow::Result;
use diesel::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;

pub fn graph_row(connection: &mut SqliteConnection, id: &str) -> Result<Option<RepositoryGraphRow>> {
    Ok(repository_graphs::table
        .find(id)
        .first::<RepositoryGraphRow>(connection)
        .optional()?
        .filter(|g| g.graph_revision.is_some()))
}
pub fn graph_summary(connection: &mut SqliteConnection, row: RepositoryGraphRow) -> Result<GraphDto> {
    let id = &row.repository_id;
    let levels: HashMap<String, i64> = graph_nodes::table
        .filter(graph_nodes::repository_id.eq(id))
        .group_by(graph_nodes::level)
        .select((graph_nodes::level, diesel::dsl::count_star()))
        .load(connection)?
        .into_iter()
        .collect();
    let level = |name: &str| *levels.get(name).unwrap_or(&0);
    let symbols = graph_symbols::table.filter(graph_symbols::repository_id.eq(id)).count().get_result(connection)?;
    let edges = graph_edges::table.filter(graph_edges::repository_id.eq(id)).count().get_result(connection)?;
    let parse_errors = graph_diagnostics::table
        .filter(graph_diagnostics::repository_id.eq(id))
        .filter(graph_diagnostics::severity.eq("error"))
        .count()
        .get_result(connection)?;
    Ok(GraphDto {
        repository_id: row.repository_id,
        graph_revision: row.graph_revision.unwrap_or_default(),
        schema_version: row.schema_version,
        indexed_at: row.indexed_at,
        root_name: row.root_name,
        root_path: row.root_path,
        imported_at: row.imported_at,
        stats: GraphStatsDto {
            files: level("file"),
            symbols,
            modules: level("module"),
            types: level("type"),
            callables: level("callable"),
            nodes: levels.values().sum(),
            edges,
            external_nodes: level("external"),
            parse_errors,
        },
    })
}
pub fn report_facts(connection: &mut SqliteConnection, row: RepositoryGraphRow) -> Result<Value> {
    let id = &row.repository_id;
    let symbols: HashMap<_, _> = graph_symbols::table
        .filter(graph_symbols::repository_id.eq(id))
        .load::<GraphSymbolRow>(connection)?
        .into_iter()
        .map(|s| (s.node_key.clone(), s))
        .collect();
    let metrics: HashMap<_, _> = graph_node_metrics::table
        .filter(graph_node_metrics::repository_id.eq(id))
        .load::<GraphNodeMetricRow>(connection)?
        .into_iter()
        .map(|m| (m.node_key.clone(), metric_value(m)))
        .collect();
    let nodes = graph_nodes::table
        .filter(graph_nodes::repository_id.eq(id))
        .order(graph_nodes::ordinal)
        .load::<GraphNodeRow>(connection)?
        .into_iter()
        .map(|n| report_node(n, &symbols, &metrics))
        .collect::<Vec<_>>();
    let edges: Vec<Value> = graph_edges::table
        .filter(graph_edges::repository_id.eq(id))
        .filter(graph_edges::relationship.ne("CONTAINS"))
        .order(graph_edges::ordinal)
        .load::<GraphEdgeRow>(connection)?
        .into_iter()
        .map(|e| edge_value(e, false))
        .collect();
    let imports: Vec<_> = edges.iter().filter(|e| e["type"] == "IMPORTS").cloned().collect();
    let diagnostics: Vec<_> = graph_diagnostics::table
        .filter(graph_diagnostics::repository_id.eq(id))
        .order(graph_diagnostics::ordinal)
        .load::<GraphDiagnosticRow>(connection)?
        .into_iter()
        .map(diagnostic_value)
        .collect();
    let candidates = graph_mutation_candidates::table
        .filter(graph_mutation_candidates::repository_id.eq(id))
        .order(graph_mutation_candidates::ordinal)
        .select(graph_mutation_candidates::payload)
        .load::<String>(connection)?
        .into_iter()
        .map(|s| serde_json::from_str::<Value>(&s))
        .collect::<std::result::Result<Vec<_>, _>>()?;
    Ok(json!({"graphRevision": row.graph_revision, "nodes": nodes, "edges": edges, "imports": imports,
        "diagnostics": diagnostics, "mutationCandidates": candidates}))
}
fn report_node(n: GraphNodeRow, symbols: &HashMap<String, GraphSymbolRow>, metrics: &HashMap<String, Value>) -> Value {
    let symbol = symbols.get(&n.node_key).cloned();
    let metric = metrics.get(&n.node_key).cloned().unwrap_or_else(|| json!({}));
    let mut value = node_value(n, symbol);
    for field in ["language", "startColumn", "endLine", "endColumn", "signature", "visibility"] {
        value.as_object_mut().unwrap().remove(field);
    }
    for name in super::graph_records::METRIC_NAMES {
        value[name] = metric[name].clone();
    }
    value
}
