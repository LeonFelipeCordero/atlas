use crate::{
    domain::{
        models::SOURCE_METRIC_NAMES,
        repositories::{GraphDto, RepositoryDto, RepositoryError, RepositoryProtocol},
    },
    paths::absolute_path,
};
use anyhow::Result;
use serde_json::{Value, json};
use std::path::Path;

pub fn analyze_folder(root: &Path) -> Result<Value> {
    crate::indexer::analyze_repository(root)
}
fn required_text(value: &str, field: &str, maximum: usize) -> Result<String> {
    let text = value.trim();
    if text.is_empty() {
        return Err(RepositoryError::new(format!("{field} is required"), 400).into());
    }
    if text.chars().count() > maximum {
        return Err(RepositoryError::new(format!("{field} must be at most {maximum} characters"), 400).into());
    }
    Ok(text.into())
}
pub struct RepositoryService {
    repository: Box<dyn RepositoryProtocol>,
}
impl RepositoryService {
    pub fn new(repository: impl RepositoryProtocol + 'static) -> Self {
        Self { repository: Box::new(repository) }
    }
    pub fn register(&mut self, input: &Value) -> Result<RepositoryDto> {
        if !input.is_object() {
            return Err(RepositoryError::new("Expected an object with name and location", 400).into());
        }
        self.repository.register(
            &required_text(input["name"].as_str().unwrap_or(""), "name", 200)?,
            &required_text(input["location"].as_str().unwrap_or(""), "location", 4096)?,
        )
    }
    pub fn list(&mut self) -> Result<Vec<RepositoryDto>> {
        self.repository.list()
    }
    fn identifier(&mut self, identifier: &str) -> Result<String> {
        let id = required_text(identifier, "repositoryId", 200)?;
        if !self.repository.exists(&id)? {
            return Err(RepositoryError::new("Repository not found", 404).into());
        }
        Ok(id)
    }
    pub fn get_architecture(&mut self, identifier: &str) -> Result<Option<GraphDto>> {
        let id = self.identifier(identifier)?;
        self.repository.graph(&id)
    }
    pub fn get_report_facts(&mut self, identifier: &str) -> Result<Option<Value>> {
        let id = self.identifier(identifier)?;
        self.repository.report_facts(&id)
    }
    pub fn report(&mut self, project_name: &str) -> Result<Value> {
        let name = required_text(project_name, "project name", 200)?;
        let id = self.repository.resolve(&name)?.ok_or_else(|| RepositoryError::new("Repository not found", 404))?;
        let facts = self
            .repository
            .report_facts(&id)?
            .ok_or_else(|| RepositoryError::new("Repository has no indexed graph; run atlas index first", 409))?;
        let mut nodes = facts["nodes"].as_array().cloned().unwrap_or_default();
        for node in &mut nodes {
            add_properties(node);
        }
        crate::metrics::report::build_artifact_report(&json!({"nodes": nodes, "edges": facts["edges"],
            "diagnostics": facts["diagnostics"], "mutationCandidates": facts["mutationCandidates"]}))
    }
    pub fn save_folder(&mut self, root: &Path, artifact: &Value) -> Result<GraphDto> {
        let root = absolute_path(root)?;
        for project in self.repository.list()? {
            if !project.location.contains("://") && absolute_path(Path::new(&project.location))? == root {
                return self.repository.save(&project.id, artifact);
            }
        }
        let base = root.file_name().unwrap_or_default().to_string_lossy().trim().chars().take(190).collect::<String>();
        let base = if base.is_empty() { "repository".into() } else { base };
        let mut name = base.clone();
        let mut suffix = 2;
        while self.repository.resolve(&name)?.is_some() {
            name = format!("{base} ({suffix})");
            suffix += 1;
        }
        self.repository.save_new(&name, &root.to_string_lossy(), artifact)
    }
    pub fn index(&mut self, project_name: &str, root: &Path) -> Result<GraphDto> {
        let name = required_text(project_name, "project name", 200)?;
        let id = self.repository.resolve(&name)?.ok_or_else(|| RepositoryError::new("Repository not found", 404))?;
        let artifact = analyze_folder(root)?;
        self.repository.save(&id, &artifact)
    }
}
fn add_properties(node: &mut Value) {
    let mut properties = json!({});
    for name in SOURCE_METRIC_NAMES {
        properties[name] = node[name].clone();
    }
    node["properties"] = properties;
}
pub fn saved_folder_report(root: &Path) -> Result<Value> {
    let root = absolute_path(root)?;
    let mut service = crate::bootstrap::repository_service(None)?;
    let projects = service
        .list()?
        .into_iter()
        .filter(|p| !p.location.contains("://"))
        .map(|p| Ok((absolute_path(Path::new(&p.location))?, p)))
        .collect::<Result<Vec<_>>>()?;
    let matching: Vec<_> = projects.into_iter().filter(|(location, _)| *location == root).collect();
    anyhow::ensure!(matching.len() == 1, "Expected one indexed project at this folder; run atlas index first");
    service.report(&matching[0].1.name)
}
