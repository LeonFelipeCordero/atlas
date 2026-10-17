use super::{navigation::NavigationService, repositories::RepositoryService};
use crate::persistence::{
    navigation::{ProjectSelector, navigation_reader},
    repositories::repository_store,
};
use anyhow::Result;
use std::path::Path;

pub fn migrate_database(path: Option<&Path>) -> Result<()> {
    crate::persistence::database::migrate_database(path)
}
pub fn repository_service(path: Option<&Path>) -> Result<RepositoryService> {
    Ok(RepositoryService::new(repository_store(path)?))
}
pub fn navigation_service(
    project: Option<&str>,
    revision: Option<&str>,
    path: Option<&Path>,
) -> Result<NavigationService> {
    let cwd = std::env::current_dir()?;
    let selector = match project {
        Some(name) => ProjectSelector::Name(name),
        None => ProjectSelector::Directory(&cwd),
    };
    Ok(NavigationService::new(navigation_reader(selector, revision, path)?))
}
