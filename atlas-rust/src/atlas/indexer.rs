//! Analyze repositories into in-memory graph artifacts.
use std::path::Path;

use anyhow::Result;

use crate::domain::models::GraphArtifact;
use crate::metrics::{artifact::build_artifact, callables::add_callable_metrics, resolver::resolve_connections};
use crate::parsing::{
    discovery::{discover_files, validate_repository},
    parser::parse_files,
};

pub fn analyze_repository(root: &Path) -> Result<GraphArtifact> {
    let root = validate_repository(root)?;
    let mut repository = parse_files(discover_files(&root)?)?;
    add_callable_metrics(&mut repository)?;
    let graph = resolve_connections(&repository)?;
    build_artifact(&root, &repository, graph)
}
