use crate::domain::repositories::RepositoryError;
use anyhow::{Context, Result};
use diesel::{connection::SimpleConnection, prelude::*, sql_types::Text};
use std::{
    collections::HashSet,
    env,
    path::{Component, Path, PathBuf},
};

const MIGRATIONS: &[(&str, &str)] = &[
    ("0001_initial", include_str!("migrations/versions/0001_initial.sql")),
    ("0002_graph_nodes", include_str!("migrations/versions/0002_graph_nodes.sql")),
    ("0003_graph_relations", include_str!("migrations/versions/0003_graph_relations.sql")),
    ("0004_drop_graph_artifact", include_str!("migrations/versions/0004_drop_graph_artifact.sql")),
    ("0005_mutation_candidates", include_str!("migrations/versions/0005_mutation_candidates.sql")),
];
#[derive(QueryableByName)]
struct Revision {
    #[diesel(sql_type = Text)]
    version_num: String,
}

pub use super::home::expand_home;
pub fn absolute_path(path: &Path) -> Result<PathBuf> {
    let expanded = expand_home(path)?;
    let absolute = if expanded.is_absolute() { expanded } else { env::current_dir()?.join(expanded) };
    resolve_components(&absolute, &mut HashSet::new())
}
fn resolve_components(path: &Path, links: &mut HashSet<PathBuf>) -> Result<PathBuf> {
    let mut resolved = PathBuf::new();
    for part in path.components() {
        match part {
            Component::ParentDir => {
                resolved.pop();
            }
            Component::CurDir => {}
            other => {
                resolved.push(other);
                resolved = resolve_link(resolved, links)?;
            }
        }
    }
    Ok(resolved)
}
fn resolve_link(path: PathBuf, links: &mut HashSet<PathBuf>) -> Result<PathBuf> {
    if !path.symlink_metadata().is_ok_and(|metadata| metadata.file_type().is_symlink()) {
        return Ok(path);
    }
    if !links.insert(path.clone()) {
        return Err(std::io::Error::from_raw_os_error(libc::ELOOP).into());
    }
    let target = std::fs::read_link(&path)?;
    let absolute = if target.is_absolute() { target } else { path.parent().unwrap_or(Path::new("/")).join(target) };
    let resolved = resolve_components(&absolute, links);
    links.remove(&path);
    resolved
}
pub fn default_database_path() -> Result<PathBuf> {
    if let Some(path) = env::var_os("DATABASE_PATH").filter(|s| !s.is_empty()) {
        return expand_home(Path::new(&path));
    }
    let data = env::var_os("XDG_DATA_HOME")
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("~/.local/share"));
    Ok(expand_home(&data)?.join("atlas/atlas.sqlite"))
}
pub fn database_path(path: Option<&Path>) -> Result<PathBuf> {
    absolute_path(&match path {
        Some(path) => path.to_path_buf(),
        None => default_database_path()?,
    })
}
pub fn create_engine(path: Option<&Path>) -> Result<SqliteConnection> {
    let target = database_path(path)?;
    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut connection = SqliteConnection::establish(&target.to_string_lossy()).map_err(storage_error)?;
    connection.batch_execute("PRAGMA busy_timeout=30000; PRAGMA foreign_keys=ON;").map_err(storage_error)?;
    Ok(connection)
}
pub fn storage_error(error: impl std::fmt::Display) -> anyhow::Error {
    RepositoryError::new(error.to_string(), 500).into()
}
pub fn migrate_database(path: Option<&Path>) -> Result<()> {
    let mut connection = create_engine(path)?;
    connection.batch_execute("PRAGMA journal_mode=WAL;").map_err(storage_error)?;
    connection
        .immediate_transaction::<_, anyhow::Error, _>(|connection| {
            connection.batch_execute(&include_str!("migrations/alembic_version.sql").replacen(
                "CREATE TABLE",
                "CREATE TABLE IF NOT EXISTS",
                1,
            ))?;
            let revisions =
                diesel::sql_query("SELECT version_num FROM alembic_version").load::<Revision>(connection)?;
            anyhow::ensure!(revisions.len() <= 1, "Multiple Alembic revisions are not supported");
            let current = revisions.first().map(|r| r.version_num.as_str());
            let start = match current {
                None => 0,
                Some(revision) => {
                    MIGRATIONS
                        .iter()
                        .position(|(id, _)| *id == revision)
                        .with_context(|| format!("Unknown Alembic revision: {revision}"))?
                        + 1
                }
            };
            for (revision, sql) in &MIGRATIONS[start..] {
                connection.batch_execute(sql)?;
                diesel::sql_query("DELETE FROM alembic_version").execute(connection)?;
                diesel::sql_query("INSERT INTO alembic_version(version_num) VALUES (?)")
                    .bind::<Text, _>(revision)
                    .execute(connection)?;
            }
            Ok(())
        })
        .map_err(storage_error)
}
pub fn repository_session(path: Option<&Path>) -> Result<SqliteConnection> {
    create_engine(path)
}
