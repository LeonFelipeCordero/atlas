use anyhow::Result;
use std::{collections::BTreeMap, fmt};

#[derive(Debug)]
pub struct UsageError {
    pub command: String,
    pub message: String,
}
impl fmt::Display for UsageError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}
impl std::error::Error for UsageError {}
pub fn usage(command: &str, message: impl Into<String>) -> anyhow::Error {
    UsageError { command: command.into(), message: message.into() }.into()
}
pub struct Options {
    pub command: String,
    pub values: BTreeMap<String, String>,
    pub positional: Vec<String>,
}
impl Options {
    pub fn parse(command: &str, args: &[String], spec: (&[&str], &[&str])) -> Result<Self> {
        let mut result = Self { command: command.into(), values: BTreeMap::new(), positional: vec![] };
        let mut args = args.iter();
        let mut literal = false;
        while let Some(argument) = args.next() {
            if !literal && argument == "--" {
                literal = true;
                continue;
            }
            if literal || !argument.starts_with('-') || argument == "-" {
                result.positional.push(argument.clone());
                continue;
            }
            result.consume_option(argument, &mut args, spec)?;
        }
        Ok(result)
    }
    pub fn parse_group<'a>(
        command: &str,
        arguments: &'a [String],
        spec: (&[&str], &[&str]),
    ) -> Result<(Self, &'a [String])> {
        let mut result = Self { command: command.into(), values: BTreeMap::new(), positional: vec![] };
        let mut args = arguments.iter();
        loop {
            let remaining = args.as_slice();
            let Some(argument) = args.next() else {
                return Ok((result, remaining));
            };
            if argument == "--" {
                return Ok((result, args.as_slice()));
            }
            if !argument.starts_with('-') || argument == "-" {
                return Ok((result, remaining));
            }
            result.consume_option(argument, &mut args, spec)?;
        }
    }
    fn consume_option(
        &mut self,
        argument: &str,
        args: &mut std::slice::Iter<'_, String>,
        spec: (&[&str], &[&str]),
    ) -> Result<()> {
        let (spelling, inline) = split_option(argument, spec.0);
        let (valued, flags) = spec;
        let option = normalize_option(spelling, valued);
        let value = if flags.contains(&option) {
            if inline.is_some() {
                return Err(usage(&self.command, format!("Option '{spelling}' does not take a value.")));
            }
            "true".into()
        } else {
            if !valued.contains(&option) {
                return Err(super::option_suggestions::unknown(&self.command, option, spec));
            }
            inline
                .map(str::to_owned)
                .or_else(|| args.next().cloned())
                .ok_or_else(|| usage(&self.command, format!("Option '{spelling}' requires an argument.")))?
        };
        self.values.insert(option.into(), value);
        Ok(())
    }
    pub fn get<'a>(&'a self, name: &str, default: &'a str) -> &'a str {
        self.values.get(name).map(String::as_str).unwrap_or(default)
    }
    pub fn has(&self, name: &str) -> bool {
        self.values.contains_key(name)
    }
    pub fn choice<'a>(&'a self, name: &str, default: &'a str, choices: &[&str]) -> Result<&'a str> {
        let value = self.get(name, default);
        if !choices.contains(&value) {
            return Err(self.invalid(
                name,
                format!(
                    "'{value}' is not one of {}.",
                    choices.iter().map(|c| format!("'{c}'")).collect::<Vec<_>>().join(", ")
                ),
            ));
        }
        Ok(value)
    }
    pub fn number(&self, name: &str, default: usize, range: (usize, usize)) -> Result<usize> {
        let (minimum, maximum) = range;
        let Some(value) = self.values.get(name) else {
            return Ok(default);
        };
        let number =
            value.parse::<i64>().map_err(|_| self.invalid(name, format!("'{value}' is not a valid integer range.")))?;
        if number < minimum as i64 || number as u64 > maximum as u64 {
            let range =
                if maximum == usize::MAX { format!("x>={minimum}") } else { format!("{minimum}<=x<={maximum}") };
            return Err(self.invalid(name, format!("{number} is not in the range {range}.")));
        }
        Ok(number as usize)
    }
    pub fn invalid(&self, name: &str, message: impl fmt::Display) -> anyhow::Error {
        usage(&self.command, format!("Invalid value for '{name}': {message}"))
    }
    pub fn arguments(&self, names: &[&str], variadic: bool) -> Result<()> {
        if self.positional.len() < names.len() {
            return Err(usage(&self.command, format!("Missing argument '{}'.", names[self.positional.len()])));
        }
        if !variadic && self.positional.len() > names.len() {
            let extras = &self.positional[names.len()..];
            let message = if extras.len() == 1 {
                format!("Got unexpected extra argument ({})", extras[0])
            } else {
                format!("Got unexpected extra arguments ({})", extras.join(" "))
            };
            return Err(usage(&self.command, message));
        }
        Ok(())
    }
}
fn split_option<'a>(argument: &'a str, valued: &[&str]) -> (&'a str, Option<&'a str>) {
    if valued.contains(&"--folder") && argument.starts_with("-f") && argument.len() > 2 {
        return ("-f", Some(&argument[2..]));
    }
    argument.split_once('=').map_or((argument, None), |(a, b)| (a, Some(b)))
}
fn normalize_option<'a>(spelling: &'a str, valued: &[&str]) -> &'a str {
    if valued.contains(&"--folder") && matches!(spelling, "-f" | "--f") { "--folder" } else { spelling }
}
pub fn json_dump(value: &serde_json::Value) -> String {
    let compact = serde_json::to_string(value).expect("JSON value serialization");
    let mut result = String::new();
    let (mut quoted, mut escaped) = (false, false);
    for character in compact.chars() {
        result.push(character);
        if escaped {
            escaped = false;
            continue;
        }
        if quoted && character == '\\' {
            escaped = true;
            continue;
        }
        if character == '"' {
            quoted = !quoted;
        }
        if !quoted && matches!(character, ',' | ':') {
            result.push(' ');
        }
    }
    result
}
