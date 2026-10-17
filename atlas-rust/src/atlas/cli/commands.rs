use super::options::{Options, UsageError, json_dump, usage};
use crate::{paths::absolute_path, services::repositories::analyze_folder};
use anyhow::Result;
use serde_json::json;
use std::path::Path;

const COMMANDS: &[&str] = &["check", "graph", "index", "mutations", "projects", "report"];

pub fn run() -> Result<i32> {
    run_args(&std::env::args().skip(1).collect::<Vec<_>>())
}
pub fn run_args(args: &[String]) -> Result<i32> {
    match dispatch(args) {
        Ok(code) => Ok(code),
        Err(error) => {
            if let Some(error) = error.downcast_ref::<UsageError>() {
                super::help::usage(error);
                return Ok(2);
            }
            eprintln!("Error: {error}");
            Ok(1)
        }
    }
}
fn dispatch(args: &[String]) -> Result<i32> {
    let (options, tail) = Options::parse_group("", args, (&[], &["--help"]))?;
    if options.has("--help") {
        super::help::print("", false);
        return Ok(0);
    }
    let Some(command) = tail.first().map(String::as_str) else {
        return missing_command(args, "");
    };
    route(command, tail)
}
fn route(command: &str, args: &[String]) -> Result<i32> {
    let tail = &args[1..];
    match command {
        "graph" => super::graph::run(tail),
        "mutations" => super::mutations::run(tail),
        "index" | "projects" | "report" | "check" => standard_command(command, tail),
        _ => unknown_group_command("", args, (&[], COMMANDS)),
    }
}
pub(super) fn unknown_group_command(group: &str, args: &[String], config: (&[&str], &[&str])) -> Result<i32> {
    // Click reparses an unknown command token before reporting group option errors or help.
    let (options, _) = Options::parse_group(group, args, (config.0, &["--help"]))?;
    if options.has("--help") {
        super::help::print(group, false);
        return Ok(0);
    }
    Err(super::option_suggestions::unknown_command(group, &args[0], config.1))
}
pub(super) fn missing_command(args: &[String], command: &str) -> Result<i32> {
    if !args.is_empty() {
        return Err(usage(command, "Missing command."));
    }
    super::help::print(command, true);
    Ok(2)
}
fn standard_command(command: &str, tail: &[String]) -> Result<i32> {
    let valued: &[&str] = match command {
        "index" => &["--folder"],
        "report" | "check" => &["--folder", "--format"],
        _ => &[],
    };
    let options = Options::parse(
        command,
        tail,
        (valued, if matches!(command, "report" | "check") { &["--save", "--help"] } else { &["--help"] }),
    )?;
    if options.has("--help") {
        super::help::print(command, false);
        return Ok(0);
    }
    options.arguments(&[], false)?;
    let format = options.choice("--format", "markdown", &["markdown", "json"])?;
    if command == "projects" {
        println!("{}", serde_json::to_string_pretty(&crate::bootstrap::repository_service(None)?.list()?)?);
        return Ok(0);
    }
    analyze_command(command, &options, format)
}
fn analyze_command(command: &str, options: &Options, format: &str) -> Result<i32> {
    let root = absolute_path(Path::new(options.get("--folder", ".")))?;
    let config = if command == "check" { Some(crate::metrics::config::load_config(&root)?) } else { None };
    let artifact = analyze_folder(&root)?;
    if command == "index" {
        let graph = crate::bootstrap::repository_service(None)?.save_folder(&root, &artifact)?;
        println!(
            "{}",
            json_dump(
                &json!({"repositoryId": graph.repository_id, "schemaVersion": graph.schema_version, "stats": graph.stats})
            )
        );
        return Ok(0);
    }
    let report = crate::metrics::report::build_artifact_report(&artifact)?;
    if options.has("--save") {
        crate::bootstrap::repository_service(None)?.save_folder(&root, &artifact)?;
    }
    if command == "report" {
        return print_report(&report, format);
    }
    print_check(&report, config.as_ref().unwrap(), format)
}
fn print_report(report: &serde_json::Value, format: &str) -> Result<i32> {
    println!(
        "{}",
        if format == "json" {
            serde_json::to_string_pretty(report)?
        } else {
            crate::metrics::report::render_markdown(report)
        }
    );
    Ok(0)
}
fn print_check(report: &serde_json::Value, config: &serde_json::Value, format: &str) -> Result<i32> {
    let check = crate::metrics::check::build_check(report, config)?;
    println!(
        "{}",
        if format == "json" {
            serde_json::to_string_pretty(&check)?
        } else {
            crate::metrics::check::render_check(&check)
        }
    );
    Ok(if check["findings"].as_array().is_some_and(|f| !f.is_empty()) { 1 } else { 0 })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn group_help_after_terminator_validates_remaining_options() {
        let cases = [
            (vec!["--", "--help", "--bogus"], "", "No such option '--bogus'."),
            (vec!["--", "--bogus"], "", "No such option '--bogus'."),
            (vec!["graph", "--", "--help", "--project"], "graph", "Option '--project' requires an argument."),
            (vec!["graph", "--", "--project", "missing"], "graph", "No such command '--project'."),
        ];
        for (args, command, message) in cases {
            let args = args.into_iter().map(String::from).collect::<Vec<_>>();
            let error = dispatch(&args).unwrap_err().downcast::<UsageError>().unwrap();
            assert_eq!(error.command, command);
            assert_eq!(error.message, message);
        }
    }
}
