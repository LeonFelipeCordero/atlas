use crate::domain::repositories::RepositoryError;
use anyhow::Result;
use sea_orm::{ConnectOptions, Database, DatabaseConnection};
use std::{
    env,
    future::Future,
    path::{Path, PathBuf},
    sync::OnceLock,
    time::Duration,
};

pub use crate::paths::{absolute_path, expand_home};

// Keep the async pool alive across synchronous CLI/repository calls.
pub(crate) fn run<F: Future>(future: F) -> F::Output {
    static RUNTIME: OnceLock<tokio::runtime::Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| tokio::runtime::Runtime::new().expect("Tokio runtime")).block_on(future)
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
pub(crate) async fn connect(target: &Path, readonly: bool) -> Result<DatabaseConnection> {
    let encoded = target.to_string_lossy().replace('%', "%25").replace('?', "%3F").replace('#', "%23");
    let mut options = ConnectOptions::new(format!("sqlite://{encoded}?mode={}", if readonly { "ro" } else { "rwc" }));
    options.max_connections(1).min_connections(1).sqlx_logging(false).connect_timeout(Duration::from_secs(30));
    let db = Database::connect(options).await.map_err(storage_error)?;
    use sea_orm::ConnectionTrait;
    db.execute_unprepared("PRAGMA busy_timeout=30000; PRAGMA foreign_keys=ON;").await.map_err(storage_error)?;
    Ok(db)
}
pub fn create_engine(path: Option<&Path>) -> Result<DatabaseConnection> {
    let target = database_path(path)?;
    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent)?;
    }
    run(connect(&target, false))
}
pub fn storage_error(error: impl std::fmt::Display) -> anyhow::Error {
    RepositoryError::new(error.to_string(), 500).into()
}
pub fn migrate_database(path: Option<&Path>) -> Result<()> {
    let connection = create_engine(path)?;
    run(super::migrations::migrate(&connection)).map_err(storage_error)
}
pub fn repository_session(path: Option<&Path>) -> Result<DatabaseConnection> {
    create_engine(path)
}
