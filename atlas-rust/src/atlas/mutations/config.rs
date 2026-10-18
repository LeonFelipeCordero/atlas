//! Strict, opt-in rule selection. Rule order and duplicates are retained.
use super::rules::validate_rules;
use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MutationConfig {
    #[serde(default)]
    pub rules: Vec<String>,
}

impl MutationConfig {
    pub fn from_value(value: &Value) -> Result<Self> {
        if !value.is_object() {
            bail!("Mutation configuration must be an object");
        }
        let config: Self = serde_json::from_value(value.clone())?;
        validate_rules(&config.rules)?;
        Ok(config)
    }
}

/// Load the mutation section from an already validated project configuration.
pub fn from_project(value: &Value) -> Result<MutationConfig> {
    let Some(project) = value.as_object() else {
        bail!("Project configuration must be an object");
    };
    project.get("mutations").map(MutationConfig::from_value).unwrap_or_else(|| Ok(MutationConfig::default()))
}
