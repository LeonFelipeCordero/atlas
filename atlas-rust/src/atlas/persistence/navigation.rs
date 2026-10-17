use super::{
    database::absolute_path, models::*, navigation_database::readonly_session, navigation_queries::*, schema::*,
};
use crate::domain::navigation::{EdgeRequest, GraphSnapshot, NavigationReader, error};
use anyhow::Result;
use diesel::{
    prelude::*,
    sql_types::{Bool, Integer, Text},
};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path};

macro_rules! node_query {
    ($id:expr) => {
        graph_nodes::table
            .left_join(
                graph_symbols::table.on(graph_symbols::repository_id
                    .eq(graph_nodes::repository_id)
                    .and(graph_symbols::node_key.eq(graph_nodes::node_key))),
            )
            .filter(graph_nodes::repository_id.eq($id))
            .select((GraphNodeRow::as_select(), Option::<GraphSymbolRow>::as_select()))
    };
}
pub struct GraphReader {
    connection: SqliteConnection,
    pub snapshot: GraphSnapshot,
}
pub enum ProjectSelector<'a> {
    Name(&'a str),
    Directory(&'a Path),
}
pub fn navigation_reader(
    project: ProjectSelector<'_>,
    revision: Option<&str>,
    path: Option<&Path>,
) -> Result<GraphReader> {
    let mut connection = readonly_session(path)?;
    let (id, location) = select_project(&mut connection, project)?;
    let graph = repository_graphs::table
        .find(&id)
        .first::<RepositoryGraphRow>(&mut connection)
        .optional()?
        .filter(|g| g.graph_revision.is_some())
        .ok_or_else(|| error("Project has no normalized graph; index it first"))?;
    let snapshot = GraphSnapshot {
        repository_id: id,
        revision: graph.graph_revision.unwrap(),
        indexed_at: graph.indexed_at,
        root: location,
    };
    if let Some(expected) = revision.filter(|r| *r != snapshot.revision) {
        return Err(error(format!("Stale graph revision: expected {expected}, current {}", snapshot.revision)));
    }
    Ok(GraphReader { connection, snapshot })
}
fn select_project(connection: &mut SqliteConnection, project: ProjectSelector<'_>) -> Result<(String, String)> {
    let rows = match project {
        ProjectSelector::Name(name) => repositories::table
            .filter(
                repositories::id.eq(name).or(diesel::dsl::sql::<Text>("lower(name)").eq(diesel::dsl::sql::<Text>(
                    "lower(",
                )
                .bind::<Text, _>(name)
                .sql(")"))),
            )
            .order(repositories::id)
            .limit(2)
            .select((repositories::id, repositories::location))
            .load(connection)?,
        ProjectSelector::Directory(directory) => containing_projects(connection, directory)?,
    };
    if rows.len() != 1 {
        return Err(error("Project not found or ambiguous; use an explicit registered project ID with --project"));
    }
    Ok(rows.into_iter().next().unwrap())
}
fn containing_projects(connection: &mut SqliteConnection, directory: &Path) -> Result<Vec<(String, String)>> {
    let current = absolute_path(directory)?;
    let mut matches = Vec::new();
    for (id, location) in
        repositories::table.select((repositories::id, repositories::location)).load::<(String, String)>(connection)?
    {
        if location.contains("://") {
            continue;
        }
        let root = absolute_path(Path::new(&location))?;
        if current.starts_with(&root) {
            matches.push((root.components().count(), id, location));
        }
    }
    if matches.is_empty() {
        return Err(error(
            "No indexed project contains the current directory; run atlas index from the repository root or use --project",
        ));
    }
    let nearest = matches.iter().map(|m| m.0).max().unwrap();
    Ok(matches.into_iter().filter(|m| m.0 == nearest).map(|(_, id, location)| (id, location)).collect())
}
fn values(rows: Vec<(GraphNodeRow, Option<GraphSymbolRow>)>) -> Vec<Value> {
    rows.into_iter().map(|(n, s)| node_value(n, s)).collect()
}
impl NavigationReader for GraphReader {
    fn snapshot(&self) -> &GraphSnapshot {
        &self.snapshot
    }
    fn overview(&mut self) -> Result<Value> {
        let id = &self.snapshot.repository_id;
        let levels: Vec<_> = graph_nodes::table
            .filter(graph_nodes::repository_id.eq(id))
            .group_by(graph_nodes::level)
            .select((graph_nodes::level, diesel::dsl::count_star()))
            .order(graph_nodes::level)
            .load::<(String, i64)>(&mut self.connection)?
            .into_iter()
            .map(|(level, count)| json!({"level": level, "count": count}))
            .collect();
        let relations: Vec<_> = graph_edges::table
            .filter(graph_edges::repository_id.eq(id))
            .group_by(graph_edges::relationship)
            .select((graph_edges::relationship, diesel::dsl::count_star()))
            .order(graph_edges::relationship)
            .load::<(String, i64)>(&mut self.connection)?
            .into_iter()
            .map(|(relation, count)| json!({"type": relation, "count": count}))
            .collect();
        let mut roots = values(
            node_query!(id)
                .filter(graph_nodes::parent_key.is_null())
                .order(graph_nodes::node_key)
                .limit(31)
                .load(&mut self.connection)?,
        );
        let truncated = roots.len() > 30;
        roots.truncate(30);
        Ok(json!({"levels": levels, "relations": relations, "roots": roots, "truncated": truncated}))
    }
    fn find(&mut self, query: &str, limit: usize) -> Result<Vec<Value>> {
        let matches = diesel::dsl::sql::<Bool>("(instr(lower(graph_nodes.path),lower(")
            .bind::<Text, _>(query)
            .sql("))>0 OR instr(lower(graph_nodes.name),lower(")
            .bind::<Text, _>(query)
            .sql("))>0 OR instr(lower(graph_nodes.qualified_name),lower(")
            .bind::<Text, _>(query)
            .sql("))>0 OR graph_nodes.node_key=")
            .bind::<Text, _>(query)
            .sql(")");
        let rank = diesel::dsl::sql::<Integer>("CASE WHEN graph_nodes.node_key=")
            .bind::<Text, _>(query)
            .sql(" THEN 0 WHEN lower(graph_nodes.path)=lower(")
            .bind::<Text, _>(query)
            .sql(") THEN CASE WHEN graph_nodes.level='file' THEN 1 ELSE 2 END WHEN lower(graph_nodes.name)=lower(")
            .bind::<Text, _>(query)
            .sql(") THEN 3 WHEN lower(graph_nodes.qualified_name)=lower(")
            .bind::<Text, _>(query)
            .sql(") THEN 4 ELSE 5 END");
        Ok(values(
            node_query!(&self.snapshot.repository_id)
                .filter(matches)
                .order((
                    rank,
                    graph_nodes::level.eq("external"),
                    diesel::dsl::sql::<Text>("coalesce(graph_nodes.path,'')"),
                    graph_nodes::name,
                    graph_nodes::node_key,
                ))
                .limit(limit as i64)
                .load(&mut self.connection)?,
        ))
    }
    fn node(&mut self, key: &str) -> Result<Value> {
        let id = &self.snapshot.repository_id;
        let row = node_query!(id)
            .filter(graph_nodes::node_key.eq(key))
            .first::<(GraphNodeRow, Option<GraphSymbolRow>)>(&mut self.connection)
            .optional()?
            .ok_or_else(|| error(format!("Node not found: {key}. Use find to obtain a stableKey.")))?;
        let mut node = node_value(row.0, row.1);
        node["external"] = json!(node["level"] == "external");
        node["metrics"] = graph_node_metrics::table
            .find((id, key))
            .first::<GraphNodeMetricRow>(&mut self.connection)
            .optional()?
            .map(metric_value)
            .unwrap_or(Value::Null);
        node["file"] = graph_files::table
            .find((id, key))
            .first::<GraphFileRow>(&mut self.connection)
            .optional()?
            .map(|f| json!({"bytes": f.byte_count, "sha256": f.sha256}))
            .unwrap_or(Value::Null);
        let mut decorators = graph_node_decorators::table
            .filter(graph_node_decorators::repository_id.eq(id))
            .filter(graph_node_decorators::node_key.eq(key))
            .select(graph_node_decorators::decorator)
            .order(graph_node_decorators::ordinal)
            .limit(101)
            .load::<String>(&mut self.connection)?;
        node["decoratorsTruncated"] = json!(decorators.len() > 100);
        decorators.truncate(100);
        node["decorators"] = json!(decorators);
        Ok(node)
    }
    fn children(&mut self, key: &str, limit: usize, offset: usize) -> Result<Vec<Value>> {
        Ok(values(
            node_query!(&self.snapshot.repository_id)
                .filter(graph_nodes::parent_key.eq(key))
                .order((graph_nodes::ordinal, graph_nodes::node_key))
                .limit(limit as i64)
                .offset(offset as i64)
                .load(&mut self.connection)?,
        ))
    }
    fn edges(&mut self, request: &EdgeRequest) -> Result<Vec<Value>> {
        let directions = match request.direction.as_str() {
            "both" => vec![true, false],
            "out" => vec![true],
            _ => vec![false],
        };
        let mut selected = BTreeMap::new();
        let batches = directions
            .into_iter()
            .flat_map(|outgoing| request.relations.iter().map(move |relation| (outgoing, relation)));
        for (outgoing, relation) in batches {
            selected.extend(
                self.adjacency(request, outgoing, relation)?
                    .into_iter()
                    .map(|edge| (edge.ordinal, edge_value(edge, true))),
            );
        }
        Ok(selected.into_values().take(request.limit).collect())
    }
    fn diagnostics(&mut self, paths: &[String], limit: usize) -> Result<Vec<Value>> {
        Ok(graph_diagnostics::table
            .filter(graph_diagnostics::repository_id.eq(&self.snapshot.repository_id))
            .filter(graph_diagnostics::path.eq_any(paths))
            .order(graph_diagnostics::ordinal)
            .limit(limit as i64)
            .load::<GraphDiagnosticRow>(&mut self.connection)?
            .into_iter()
            .map(diagnostic_value)
            .collect())
    }
    fn file(&mut self, path: &str) -> Result<Vec<Value>> {
        Ok(graph_nodes::table
            .inner_join(
                graph_files::table.on(graph_files::repository_id
                    .eq(graph_nodes::repository_id)
                    .and(graph_files::node_key.eq(graph_nodes::node_key))),
            )
            .filter(graph_nodes::repository_id.eq(&self.snapshot.repository_id))
            .filter(graph_nodes::path.eq(path))
            .order(graph_nodes::node_key)
            .select((graph_nodes::node_key, graph_files::sha256))
            .limit(2)
            .load::<(String, Option<String>)>(&mut self.connection)?
            .into_iter()
            .map(|(key, hash)| json!({"stableKey": key, "sha256": hash}))
            .collect())
    }
}
impl GraphReader {
    fn adjacency(&mut self, request: &EdgeRequest, outgoing: bool, relation: &str) -> Result<Vec<GraphEdgeRow>> {
        let mut query = graph_edges::table
            .filter(graph_edges::repository_id.eq(&self.snapshot.repository_id))
            .filter(graph_edges::relationship.eq(relation))
            .into_boxed();
        query = if outgoing {
            query.filter(graph_edges::source_key.eq(&request.key))
        } else {
            query.filter(graph_edges::target_key.eq(&request.key))
        };
        Ok(query.order(graph_edges::ordinal).limit(request.limit as i64).load(&mut self.connection)?)
    }
}
