use super::help_wrap::{short_help, wrap};
use serde::Deserialize;
use std::{collections::BTreeMap, sync::LazyLock};

#[derive(Deserialize)]
struct Definition {
    usage: String,
    description: String,
    options: Vec<[String; 2]>,
    #[serde(default)]
    commands: Vec<[String; 2]>,
}
static DEFINITIONS: LazyLock<BTreeMap<String, Definition>> =
    LazyLock::new(|| serde_json::from_str(include_str!("help/definitions.json")).unwrap());
pub fn text(command: &str) -> String {
    render(command, terminal_width())
}
pub fn render(command: &str, width: usize) -> String {
    let definition = DEFINITIONS.get(command).unwrap_or(&DEFINITIONS[""]);
    let mut output = format!("{}\n", definition.usage);
    description(&mut output, &definition.description, width);
    section(&mut output, "Options", (&definition.options, width));
    if !definition.commands.is_empty() {
        let longest = definition.commands.iter().map(|r| r[0].len()).max().unwrap_or(0);
        let rows: Vec<_> =
            definition.commands.iter().map(|r| [r[0].clone(), short_help(&r[1], width - 6 - longest)]).collect();
        section(&mut output, "Commands", (&rows, width));
    }
    output
}
fn description(output: &mut String, text: &str, width: usize) {
    for paragraph in text.split("\n\n").filter(|p| !p.is_empty()) {
        paragraph_text(output, paragraph, width);
    }
}
fn paragraph_text(output: &mut String, paragraph: &str, width: usize) {
    output.push('\n');
    for line in wrap(&paragraph.replace('\n', " "), width - 2) {
        output.push_str(&format!("  {line}\n"));
    }
}
fn section(output: &mut String, name: &str, contents: (&[[String; 2]], usize)) {
    let (rows, width) = contents;
    if rows.is_empty() {
        return;
    }
    output.push_str(&format!("\n{name}:\n"));
    let first_column = rows.iter().map(|r| r[0].len()).max().unwrap_or(0).min(30) + 2;
    for row in rows {
        definition_row(output, row, (first_column, width));
    }
}
fn definition_row(output: &mut String, row: &[String; 2], dimensions: (usize, usize)) {
    let (first_column, width) = dimensions;
    output.push_str(&format!("  {}", row[0]));
    if row[1].is_empty() {
        output.push('\n');
        return;
    }
    if row[0].len() > first_column - 2 {
        output.push('\n');
        output.push_str(&" ".repeat(first_column + 2));
    } else {
        output.push_str(&" ".repeat(first_column - row[0].len()));
    }
    let lines = wrap(&row[1], width.saturating_sub(first_column + 2).max(10));
    output.push_str(&lines.join(&format!("\n{}", " ".repeat(first_column + 2))));
    output.push('\n');
}
fn terminal_width() -> usize {
    let columns = std::env::var("COLUMNS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .filter(|n| *n > 0)
        .unwrap_or_else(terminal_columns);
    width_for_columns(columns)
}
fn width_for_columns(columns: usize) -> usize {
    columns.min(80).saturating_sub(2).max(50)
}
fn terminal_columns() -> usize {
    let mut size = std::mem::MaybeUninit::<libc::winsize>::zeroed();
    let result = unsafe { libc::ioctl(libc::STDOUT_FILENO, libc::TIOCGWINSZ, size.as_mut_ptr()) };
    let columns = if result == 0 { usize::from(unsafe { size.assume_init() }.ws_col) } else { 0 };
    if columns == 0 { 80 } else { columns }
}
pub fn print(command: &str, stderr: bool) {
    if stderr {
        eprint!("{}", text(command));
    } else {
        print!("{}", text(command));
    }
}
pub fn usage(error: &super::options::UsageError) {
    if error.message.starts_with("Option '") {
        eprintln!("Error: {}", error.message);
        return;
    }
    let command = if error.command.is_empty() { String::new() } else { format!(" {}", error.command) };
    let definition = DEFINITIONS.get(&error.command).unwrap_or(&DEFINITIONS[""]);
    eprintln!("{}\nTry 'atlas{command} --help' for help.\n\nError: {}", definition.usage, error.message);
}
#[cfg(test)]
mod tests {
    #[test]
    fn default_help_matches_live_non_tty_output() {
        let snapshots = [
            ("", include_str!("help/main.txt")),
            ("graph", include_str!("help/graph.txt")),
            ("index", include_str!("help/index.txt")),
            ("projects", include_str!("help/projects.txt")),
            ("report", include_str!("help/report.txt")),
            ("check", include_str!("help/check.txt")),
            ("mutations", include_str!("help/mutations.txt")),
            ("mutations run", include_str!("help/mutations-run.txt")),
            ("graph overview", include_str!("help/graph-overview.txt")),
            ("graph find", include_str!("help/graph-find.txt")),
            ("graph show", include_str!("help/graph-show.txt")),
            ("graph children", include_str!("help/graph-children.txt")),
            ("graph context", include_str!("help/graph-context.txt")),
            ("graph path", include_str!("help/graph-path.txt")),
            ("graph source", include_str!("help/graph-source.txt")),
        ];
        for (command, expected) in snapshots {
            assert_eq!(super::render(command, 78), expected, "{command}");
        }
        assert!(super::render("graph", 50).contains("  --project TEXT   Registered project name or ID;\n"));
    }
    #[test]
    fn columns_40_80_120_match_click_bounds_and_wrapping() {
        for columns in [40, 80, 120] {
            let width = super::width_for_columns(columns);
            let rendered = super::render("graph", width);
            assert!(rendered.lines().all(|line| line.len() <= width));
            if columns == 40 {
                assert_eq!(width, 50);
                assert!(rendered.contains("  --project TEXT   Registered project name or ID;\n"));
            } else {
                assert_eq!(width, 78);
                assert_eq!(rendered, include_str!("help/graph.txt"));
            }
        }
    }
}
