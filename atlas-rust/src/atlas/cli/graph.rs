use super::{
    graph_options::GraphOptions,
    graph_output::graph_output,
    graph_source_output::source_text,
    options::{Options, json_dump},
};
use anyhow::Result;
use serde_json::Value;

const COMMANDS: &[&str] = &["children", "context", "find", "overview", "path", "show", "source"];
pub fn run(args: &[String]) -> Result<i32> {
    let (selection, tail) = Options::parse_group("graph", args, (&["--project", "--revision"], &["--help"]))?;
    if selection.has("--help") {
        super::help::print("graph", false);
        return Ok(0);
    }
    let Some(command) = tail.first().map(String::as_str) else {
        return super::commands::missing_command(args, "graph");
    };
    if !COMMANDS.contains(&command) {
        return super::commands::unknown_group_command("graph", tail, (&["--project", "--revision"], COMMANDS));
    }
    let tail = &tail[1..];
    let Some(options) = GraphOptions::parse(command, tail)? else {
        super::help::print(&format!("graph {command}"), false);
        return Ok(0);
    };
    emit(execute(options, &selection))
}
fn emit(output: Result<(Value, bool)>) -> Result<i32> {
    match output {
        Ok((payload, text)) => {
            let projected = graph_output(&payload);
            println!("{}", if text { source_text(&projected) } else { json_dump(&projected) });
            Ok(0)
        }
        Err(error) if error.downcast_ref::<super::options::UsageError>().is_some() => Err(error),
        Err(error) => {
            eprintln!("{}", json_dump(&serde_json::json!({"error": error.to_string()})));
            Ok(1)
        }
    }
}
fn execute(options: GraphOptions, selection: &Options) -> Result<(Value, bool)> {
    let mut service = crate::bootstrap::navigation_service(
        selection.values.get("--project").map(String::as_str),
        selection.values.get("--revision").map(String::as_str),
        None,
    )?;
    Ok((options.operation.execute(&mut service)?, options.text))
}
