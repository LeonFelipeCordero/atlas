use super::models::*;
use anyhow::Result;
use sea_orm::{ConnectionTrait, DbBackend, DbErr, Statement, Value};

// Fixed SQL lets SQLx reuse prepared statements without rebuilding an ORM query for every row.
async fn execute<const N: usize>(connection: &impl ConnectionTrait, sql: &str, values: [Value; N]) -> Result<()> {
    let result = connection.execute(Statement::from_sql_and_values(DbBackend::Sqlite, sql, values)).await?;
    if result.rows_affected() == 0 {
        return Err(DbErr::RecordNotInserted.into());
    }
    Ok(())
}

pub(super) async fn node(connection: &impl ConnectionTrait, r: GraphNodeRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_nodes (repository_id, node_key, parent_key, ordinal, type, kind, level, name, \
         language, qualified_name, path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.node_key.into(),
            r.parent_key.into(),
            r.ordinal.into(),
            r.type_.into(),
            r.kind.into(),
            r.level.into(),
            r.name.into(),
            r.language.into(),
            r.qualified_name.into(),
            r.path.into(),
        ],
    )
    .await
}

pub(super) async fn file(connection: &impl ConnectionTrait, r: GraphFileRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_files (repository_id, node_key, byte_count, sha256) VALUES (?, ?, ?, ?)",
        [r.repository_id.into(), r.node_key.into(), r.byte_count.into(), r.sha256.into()],
    )
    .await
}

pub(super) async fn symbol(connection: &impl ConnectionTrait, r: GraphSymbolRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_symbols (repository_id, node_key, start_line, start_column, end_line, end_column, \
         signature, visibility) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.node_key.into(),
            r.start_line.into(),
            r.start_column.into(),
            r.end_line.into(),
            r.end_column.into(),
            r.signature.into(),
            r.visibility.into(),
        ],
    )
    .await
}

pub(super) async fn metric(connection: &impl ConnectionTrait, r: GraphNodeMetricRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_node_metrics (repository_id, node_key, line_count, parameter_count, base_complexity, \
         nested_complexity, loop_complexity, total_complexity, max_decision_depth) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.node_key.into(),
            r.line_count.into(),
            r.parameter_count.into(),
            r.base_complexity.into(),
            r.nested_complexity.into(),
            r.loop_complexity.into(),
            r.total_complexity.into(),
            r.max_decision_depth.into(),
        ],
    )
    .await
}

pub(super) async fn decorator(connection: &impl ConnectionTrait, r: GraphNodeDecoratorRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_node_decorators (repository_id, node_key, ordinal, decorator) VALUES (?, ?, ?, ?)",
        [r.repository_id.into(), r.node_key.into(), r.ordinal.into(), r.decorator.into()],
    )
    .await
}

pub(super) async fn edge(connection: &impl ConnectionTrait, r: GraphEdgeRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_edges (repository_id, ordinal, source_key, target_key, relationship, confidence, \
         path, evidence, line, type_only) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.ordinal.into(),
            r.source_key.into(),
            r.target_key.into(),
            r.relationship.into(),
            r.confidence.into(),
            r.path.into(),
            r.evidence.into(),
            r.line.into(),
            r.type_only.into(),
        ],
    )
    .await
}

pub(super) async fn diagnostic(connection: &impl ConnectionTrait, r: GraphDiagnosticRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_diagnostics (repository_id, ordinal, severity, path, language, message) \
         VALUES (?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.ordinal.into(),
            r.severity.into(),
            r.path.into(),
            r.language.into(),
            r.message.into(),
        ],
    )
    .await
}

pub(super) async fn candidate(connection: &impl ConnectionTrait, r: GraphMutationCandidateRow) -> Result<()> {
    execute(
        connection,
        "INSERT INTO graph_mutation_candidates (repository_id, candidate_id, file_key, ordinal, path, \
         language, source_hash, kind, operator, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            r.repository_id.into(),
            r.candidate_id.into(),
            r.file_key.into(),
            r.ordinal.into(),
            r.path.into(),
            r.language.into(),
            r.source_hash.into(),
            r.kind.into(),
            r.operator.into(),
            r.payload.into(),
        ],
    )
    .await
}
