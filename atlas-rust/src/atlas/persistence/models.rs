use super::schema::*;
use diesel::prelude::*;

#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = repositories)]
pub struct RepositoryRow {
    pub id: String,
    pub name: String,
    pub location: String,
    pub created_at: i64,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = repository_graphs)]
pub struct RepositoryGraphRow {
    pub repository_id: String,
    pub imported_at: i64,
    pub graph_revision: Option<String>,
    pub schema_version: Option<i64>,
    pub indexed_at: Option<String>,
    pub root_name: Option<String>,
    pub root_path: Option<String>,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_nodes)]
pub struct GraphNodeRow {
    pub repository_id: String,
    pub node_key: String,
    pub parent_key: Option<String>,
    pub ordinal: i64,
    pub type_: String,
    pub kind: String,
    pub level: String,
    pub name: String,
    pub language: Option<String>,
    pub qualified_name: Option<String>,
    pub path: Option<String>,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_files)]
pub struct GraphFileRow {
    pub repository_id: String,
    pub node_key: String,
    pub byte_count: Option<i64>,
    pub sha256: Option<String>,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_symbols)]
pub struct GraphSymbolRow {
    pub repository_id: String,
    pub node_key: String,
    pub start_line: Option<i64>,
    pub start_column: Option<i64>,
    pub end_line: Option<i64>,
    pub end_column: Option<i64>,
    pub signature: Option<String>,
    pub visibility: Option<String>,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_node_metrics)]
pub struct GraphNodeMetricRow {
    pub repository_id: String,
    pub node_key: String,
    pub line_count: Option<i64>,
    pub parameter_count: Option<i64>,
    pub base_complexity: Option<i64>,
    pub nested_complexity: Option<i64>,
    pub loop_complexity: Option<i64>,
    pub total_complexity: Option<i64>,
    pub max_decision_depth: Option<i64>,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_node_decorators)]
pub struct GraphNodeDecoratorRow {
    pub repository_id: String,
    pub node_key: String,
    pub ordinal: i64,
    pub decorator: String,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_edges)]
pub struct GraphEdgeRow {
    pub repository_id: String,
    pub ordinal: i64,
    pub source_key: String,
    pub target_key: String,
    pub relationship: String,
    pub confidence: String,
    pub path: Option<String>,
    pub evidence: Option<String>,
    pub line: Option<i64>,
    pub type_only: bool,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_diagnostics)]
pub struct GraphDiagnosticRow {
    pub repository_id: String,
    pub ordinal: i64,
    pub severity: String,
    pub path: String,
    pub language: String,
    pub message: String,
}
#[derive(Clone, Debug, Queryable, Selectable, Insertable)]
#[diesel(table_name = graph_mutation_candidates)]
pub struct GraphMutationCandidateRow {
    pub repository_id: String,
    pub candidate_id: String,
    pub file_key: String,
    pub ordinal: i64,
    pub path: String,
    pub language: String,
    pub source_hash: String,
    pub kind: String,
    pub operator: Option<String>,
    pub payload: String,
}
