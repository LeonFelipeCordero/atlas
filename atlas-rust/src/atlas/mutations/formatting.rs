//! Python-compatible result and progress formatting.
use serde_json::Value;

pub fn python_json(value: &Value) -> String {
    match value {
        Value::Array(items) => format!("[{}]", items.iter().map(python_json).collect::<Vec<_>>().join(", ")),
        Value::Object(items) => format!(
            "{{{}}}",
            items
                .iter()
                .map(|(key, value)| format!("{}: {}", serde_json::to_string(key).unwrap(), python_json(value)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        _ => value.to_string(),
    }
}
pub fn text<'a>(value: &'a Value, name: &str) -> &'a str {
    value[name].as_str().unwrap_or("")
}
pub fn error_suffix(value: &Value) -> String {
    value.get("error").and_then(Value::as_str).map(|error| format!("; {error}")).unwrap_or_default()
}
pub fn shell_join(arguments: &[String]) -> String {
    arguments
        .iter()
        .map(|arg| {
            if !arg.is_empty() && arg.bytes().all(|ch| ch.is_ascii_alphanumeric() || b"_@%+=:,./-".contains(&ch)) {
                arg.clone()
            } else {
                format!("'{}'", arg.replace('\'', "'\"'\"'"))
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}
pub fn repr(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') { '"' } else { '\'' };
    let escaped: String = value.chars().map(|ch| character(ch, quote)).collect();
    format!("{quote}{escaped}{quote}")
}
fn character(ch: char, quote: char) -> String {
    match ch {
        '\\' => "\\\\".into(),
        '\n' => "\\n".into(),
        '\r' => "\\r".into(),
        '\t' => "\\t".into(),
        ch if ch == quote => format!("\\{ch}"),
        ch if ch.is_control() => format!("\\x{:02x}", ch as u32),
        ch => ch.to_string(),
    }
}
pub fn io_error(error: std::io::Error) -> anyhow::Error {
    let Some(code) = error.raw_os_error() else { return error.into() };
    let message = error.to_string();
    let message = message.split(" (os error ").next().unwrap();
    anyhow::anyhow!("[Errno {code}] {message}")
}

pub fn command_error(error: std::io::Error, command: &str) -> anyhow::Error {
    if error.raw_os_error().is_none() {
        return error.into();
    }
    anyhow::anyhow!("{}: {}", io_error(error), repr(command))
}
