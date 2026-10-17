use anyhow::{Result, bail, ensure};
use diesel::{
    prelude::*,
    sql_types::{Double, Text},
};
use serde_json::Value;

pub struct GraphMetadata {
    pub schema_version: Option<i64>,
    pub indexed_at: Option<String>,
    pub root_name: Option<String>,
    pub root_path: Option<String>,
}
pub fn falsey(value: &Value) -> bool {
    match value {
        Value::Null => true,
        Value::Bool(value) => !value,
        Value::Number(number) => number.as_f64() == Some(0.0),
        Value::String(value) => value.is_empty(),
        Value::Array(value) => value.is_empty(),
        Value::Object(value) => value.is_empty(),
    }
}
pub fn optional_mapping(value: &Value, name: &str) -> Result<()> {
    ensure!(value.is_object() || falsey(value), "Graph {name} must be an object or empty");
    Ok(())
}
impl GraphMetadata {
    pub fn read(connection: &mut SqliteConnection, artifact: &Value) -> Result<Self> {
        let repository = &artifact["repository"];
        optional_mapping(repository, "repository")?;
        Ok(Self {
            schema_version: integer(&artifact["schemaVersion"])?,
            indexed_at: scalar_text(connection, &repository["indexedAt"])?,
            root_name: scalar_text(connection, &repository["name"])?,
            root_path: scalar_text(connection, &repository["path"])?,
        })
    }
}
fn scalar_text(connection: &mut SqliteConnection, value: &Value) -> Result<Option<String>> {
    let result = match value {
        Value::Null => return Ok(None),
        Value::String(value) => value.clone(),
        Value::Bool(value) => i32::from(*value).to_string(),
        Value::Number(number) => numeric_text(connection, number)?,
        _ => bail!("Graph metadata fields must be SQLite scalar values or null"),
    };
    Ok(Some(result))
}
fn numeric_text(connection: &mut SqliteConnection, number: &serde_json::Number) -> Result<String> {
    if let Some(integer) = number.as_i64() {
        return Ok(integer.to_string());
    }
    ensure!(number.to_string().contains(['.', 'e', 'E']), "Graph metadata integer exceeds SQLite range");
    let real = number.as_f64().ok_or_else(|| anyhow::anyhow!("Graph metadata number exceeds SQLite range"))?;
    Ok(diesel::select(diesel::dsl::sql::<Text>("CAST(").bind::<Double, _>(real).sql(" AS TEXT)"))
        .get_result(connection)?)
}
fn integer(value: &Value) -> Result<Option<i64>> {
    match value {
        Value::Null => Ok(None),
        Value::Bool(value) => Ok(Some(i64::from(*value))),
        Value::Number(number) => parse_integer(&number.to_string()).map(Some),
        Value::String(text) => parse_integer(text).map(Some),
        _ => bail!("Graph schemaVersion must be an integer or null"),
    }
}
fn parse_integer(text: &str) -> Result<i64> {
    if let Ok(integer) = text.trim().parse::<i64>() {
        return Ok(integer);
    }
    let real = text.trim().parse::<f64>()?;
    ensure!(
        real.is_finite() && real.fract() == 0.0 && real >= i64::MIN as f64 && real < -(i64::MIN as f64),
        "Graph schemaVersion must be a SQLite integer"
    );
    Ok(real as i64)
}
