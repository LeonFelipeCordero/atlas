use super::database::database_path;
use crate::domain::navigation::error;
use anyhow::Result;
use diesel::{connection::SimpleConnection, prelude::*, sql_types::Text};
use std::{collections::BTreeSet, path::Path};

const REQUIRED_TABLES: &[&str] = &[
    "repositories",
    "repository_graphs",
    "graph_nodes",
    "graph_files",
    "graph_symbols",
    "graph_node_metrics",
    "graph_node_decorators",
    "graph_edges",
    "graph_diagnostics",
];
const REQUIRED_INDEXES: &[&str] = &[
    "graph_nodes_parent",
    "graph_nodes_name",
    "graph_nodes_path",
    "graph_edges_source",
    "graph_edges_target",
    "graph_diagnostics_path",
];
#[derive(QueryableByName)]
struct SchemaName {
    #[diesel(sql_type = Text)]
    name: String,
}
fn check_schema(connection: &mut SqliteConnection) -> Result<()> {
    let names: BTreeSet<String> = diesel::sql_query("SELECT name FROM sqlite_master WHERE type IN ('table','index')")
        .load::<SchemaName>(connection)?
        .into_iter()
        .map(|s| s.name)
        .collect();
    let missing: BTreeSet<&str> =
        REQUIRED_TABLES.iter().chain(REQUIRED_INDEXES).copied().filter(|n| !names.contains(*n)).collect();
    if !missing.is_empty() {
        return Err(error(format!(
            "Missing graph schema/index: {}. Explicitly migrate and index the project.",
            missing.into_iter().collect::<Vec<_>>().join(", ")
        )));
    }
    Ok(())
}
fn uri_path(path: &Path) -> String {
    let text = path.to_string_lossy();
    let encoded = text.replace('%', "%25").replace('?', "%3F").replace('#', "%23");
    format!("file:{encoded}?mode=ro")
}
pub fn readonly_session(path: Option<&Path>) -> Result<SqliteConnection> {
    let target = database_path(path)?;
    let read_error = |e: String| {
        error(format!(
            "Cannot read graph database {}: {e}. Index the project after explicitly migrating the database.",
            target.display()
        ))
    };
    let mut connection = SqliteConnection::establish(&uri_path(&target)).map_err(|e| {
        let message = match e {
            diesel::ConnectionError::BadConnection(message) => format!(
                "(sqlite3.OperationalError) {message}\n(Background on this error at: https://sqlalche.me/e/21/e3q8)"
            ),
            other => other.to_string(),
        };
        read_error(message)
    })?;
    connection.batch_execute("PRAGMA query_only=ON; BEGIN;").map_err(|e| read_error(e.to_string()))?;
    check_schema(&mut connection)?;
    Ok(connection)
}
