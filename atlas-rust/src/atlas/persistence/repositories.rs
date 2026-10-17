use super::{
    database::{create_engine, storage_error},
    graph_queries,
    graph_records::*,
    models::*,
    schema::*,
};
use crate::domain::repositories::{GraphDto, RepositoryDto, RepositoryError, RepositoryProtocol};
use anyhow::Result;
use diesel::{prelude::*, sql_types::Text};
use serde_json::Value;
use std::{
    path::Path,
    time::{SystemTime, UNIX_EPOCH},
};

pub struct RepositoryStore {
    pub(crate) connection: SqliteConnection,
}
pub fn repository_store(path: Option<&Path>) -> Result<RepositoryStore> {
    Ok(RepositoryStore { connection: create_engine(path)? })
}
fn now() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as i64
}
fn uuid(compact: bool) -> Result<String> {
    let mut data = [0u8; 16];
    getrandom::fill(&mut data)?;
    data[6] = (data[6] & 15) | 64;
    data[8] = (data[8] & 63) | 128;
    let hex: String = data.iter().map(|b| format!("{b:02x}")).collect();
    Ok(if compact {
        hex
    } else {
        format!("{}-{}-{}-{}-{}", &hex[..8], &hex[8..12], &hex[12..16], &hex[16..20], &hex[20..])
    })
}
fn dto(r: RepositoryRow, imported_at: Option<i64>) -> RepositoryDto {
    RepositoryDto { id: r.id, name: r.name, location: r.location, created_at: r.created_at, imported_at }
}
fn registration(name: &str, location: &str) -> Result<RepositoryRow> {
    Ok(RepositoryRow { id: uuid(false)?, name: name.into(), location: location.into(), created_at: now() })
}
fn duplicate_error(error: diesel::result::Error) -> anyhow::Error {
    let message = error.to_string();
    if message.contains("repositories_name_unique") || message.contains("repositories.name") {
        return RepositoryError::new("A repository with this name already exists", 409).into();
    }
    storage_error(error)
}
impl RepositoryProtocol for RepositoryStore {
    fn register(&mut self, name: &str, location: &str) -> Result<RepositoryDto> {
        let row = registration(name, location)?;
        self.connection
            .transaction::<_, diesel::result::Error, _>(|c| {
                diesel::insert_into(repositories::table).values(&row).execute(c)
            })
            .map_err(duplicate_error)?;
        Ok(dto(row, None))
    }
    fn list(&mut self) -> Result<Vec<RepositoryDto>> {
        let records = repositories::table
            .left_join(repository_graphs::table.on(repository_graphs::repository_id.eq(repositories::id)))
            .select((RepositoryRow::as_select(), Option::<RepositoryGraphRow>::as_select()))
            .order((repositories::created_at, repositories::id))
            .load::<(RepositoryRow, Option<RepositoryGraphRow>)>(&mut self.connection)
            .map_err(storage_error)?;
        Ok(records
            .into_iter()
            .map(|(r, g)| dto(r, g.filter(|g| g.graph_revision.is_some()).map(|g| g.imported_at)))
            .collect())
    }
    fn exists(&mut self, identifier: &str) -> Result<bool> {
        Ok(repositories::table
            .find(identifier)
            .select(repositories::id)
            .first::<String>(&mut self.connection)
            .optional()
            .map_err(storage_error)?
            .is_some())
    }
    fn resolve(&mut self, name: &str) -> Result<Option<String>> {
        repositories::table
            .filter(
                diesel::dsl::sql::<Text>("lower(name)")
                    .eq(diesel::dsl::sql::<Text>("lower(").bind::<Text, _>(name).sql(")")),
            )
            .select(repositories::id)
            .first(&mut self.connection)
            .optional()
            .map_err(storage_error)
    }
    fn graph(&mut self, identifier: &str) -> Result<Option<GraphDto>> {
        self.connection
            .transaction(|c| {
                graph_queries::graph_row(c, identifier)?.map(|g| graph_queries::graph_summary(c, g)).transpose()
            })
            .map_err(storage_error)
    }
    fn report_facts(&mut self, identifier: &str) -> Result<Option<Value>> {
        self.connection
            .transaction(|c| {
                graph_queries::graph_row(c, identifier)?.map(|g| graph_queries::report_facts(c, g)).transpose()
            })
            .map_err(storage_error)
    }
    fn save(&mut self, identifier: &str, artifact: &Value) -> Result<GraphDto> {
        validate_parentage(artifact)?;
        self.connection.transaction(|c| save_graph(c, identifier, artifact)).map_err(storage_error)
    }
    fn save_new(&mut self, name: &str, location: &str, artifact: &Value) -> Result<GraphDto> {
        validate_parentage(artifact)?;
        let row = registration(name, location)?;
        self.connection
            .transaction(|c| {
                diesel::insert_into(repositories::table).values(&row).execute(c)?;
                save_graph(c, &row.id, artifact)
            })
            .map_err(storage_error)
    }
}
fn save_graph(connection: &mut SqliteConnection, id: &str, artifact: &Value) -> Result<GraphDto> {
    let metadata = super::graph_metadata::GraphMetadata::read(connection, artifact)?;
    let row = RepositoryGraphRow {
        repository_id: id.into(),
        imported_at: now(),
        graph_revision: Some(uuid(true)?),
        schema_version: metadata.schema_version,
        indexed_at: metadata.indexed_at,
        root_name: metadata.root_name,
        root_path: metadata.root_path,
    };
    diesel::insert_into(repository_graphs::table)
        .values(&row)
        .on_conflict(repository_graphs::repository_id)
        .do_update()
        .set((
            repository_graphs::imported_at.eq(row.imported_at),
            repository_graphs::graph_revision.eq(&row.graph_revision),
            repository_graphs::schema_version.eq(row.schema_version),
            repository_graphs::indexed_at.eq(&row.indexed_at),
            repository_graphs::root_name.eq(&row.root_name),
            repository_graphs::root_path.eq(&row.root_path),
        ))
        .execute(connection)?;
    replace_graph(connection, id, artifact)?;
    graph_queries::graph_summary(connection, row)
}
fn replace_graph(connection: &mut SqliteConnection, id: &str, artifact: &Value) -> Result<()> {
    diesel::delete(graph_edges::table.filter(graph_edges::repository_id.eq(id))).execute(connection)?;
    diesel::delete(graph_nodes::table.filter(graph_nodes::repository_id.eq(id))).execute(connection)?;
    diesel::delete(graph_diagnostics::table.filter(graph_diagnostics::repository_id.eq(id))).execute(connection)?;
    for (ordinal, n) in collection(artifact, "nodes").iter().enumerate() {
        diesel::insert_into(graph_nodes::table).values(node_record(id, ordinal, n)?).execute(connection)?;
    }
    for n in collection(artifact, "nodes") {
        insert_node_details(connection, id, n)?;
    }
    insert_candidates(connection, id, artifact)?;
    insert_edges(connection, id, artifact)?;
    insert_diagnostics(connection, id, artifact)
}
