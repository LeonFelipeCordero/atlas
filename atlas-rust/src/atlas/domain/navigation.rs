use anyhow::Result;
use serde_json::{Value, json};
use std::fmt;

pub type Record = Value;
#[derive(Debug)]
pub struct NavigationError(pub String);
impl fmt::Display for NavigationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for NavigationError {}
pub fn error(message: impl Into<String>) -> anyhow::Error {
    NavigationError(message.into()).into()
}

#[derive(Clone, Debug)]
pub struct GraphSnapshot {
    pub repository_id: String,
    pub revision: String,
    pub indexed_at: Option<String>,
    pub root: String,
}
impl GraphSnapshot {
    pub fn metadata(&self) -> Value {
        json!({"repositoryId": self.repository_id, "graphRevision": self.revision, "indexedAt": self.indexed_at})
    }
}
#[derive(Clone, Debug)]
pub struct EdgeRequest {
    pub key: String,
    pub direction: String,
    pub relations: Vec<String>,
    pub limit: usize,
}
#[derive(Clone, Debug)]
pub struct TraversalRequest {
    pub key: String,
    pub direction: String,
    pub relations: Vec<String>,
    pub depth: usize,
    pub max_nodes: usize,
    pub max_edges: usize,
}
#[derive(Clone, Debug)]
pub struct PathRequest {
    pub target: String,
    pub traversal: TraversalRequest,
}
#[derive(Clone, Debug)]
pub struct SourceOptions {
    pub max_lines: usize,
    pub start_line: Option<serde_json::Number>,
}

pub trait NavigationReader {
    fn snapshot(&self) -> &GraphSnapshot;
    fn overview(&mut self) -> Result<Value>;
    fn find(&mut self, query: &str, limit: usize) -> Result<Vec<Value>>;
    fn node(&mut self, key: &str) -> Result<Value>;
    fn children(&mut self, key: &str, limit: usize, offset: usize) -> Result<Vec<Value>>;
    fn edges(&mut self, request: &EdgeRequest) -> Result<Vec<Value>>;
    fn diagnostics(&mut self, paths: &[String], limit: usize) -> Result<Vec<Value>>;
    fn file(&mut self, path: &str) -> Result<Vec<Value>>;
}
