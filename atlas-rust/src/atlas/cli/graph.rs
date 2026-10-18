use super::{
    graph_options::GraphOptions,
    graph_output::graph_output,
    graph_source_output::source_text,
    options::{Options, json_dump},
};
use anyhow::Result;
use serde_json::Value;

pub fn run(matches: &clap::ArgMatches) -> Result<i32> {
    let selection = Options::from_matches("graph", matches);
    let (command, matches) = matches.subcommand().expect("clap requires a graph command");
    let options = GraphOptions::from_matches(command, matches)?;
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
