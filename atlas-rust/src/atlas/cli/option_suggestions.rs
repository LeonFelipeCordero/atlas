use super::{integers::repr, options::usage};

pub fn unknown(command: &str, option: &str, spec: (&[&str], &[&str])) -> anyhow::Error {
    if let Some(character) = short_option(option) {
        return usage(command, format!("No such option {}.", repr(&format!("-{character}"))));
    }
    let mut candidates: Vec<_> = spec.0.iter().chain(spec.1).copied().chain(["--help"]).collect();
    if candidates.contains(&"--folder") && command != "mutations run" {
        candidates.push("--f");
    }
    candidates.sort();
    candidates.dedup();
    usage(command, format!("No such option {}.{}", repr(option), suggestions(option, &candidates)))
}
pub fn unknown_command(group: &str, command: &str, candidates: &[&str]) -> anyhow::Error {
    usage(group, format!("No such command {}.{}", repr(command), suggestions(command, candidates)))
}
fn suggestions(input: &str, candidates: &[&str]) -> String {
    let mut ranked: Vec<_> = candidates
        .iter()
        .copied()
        .map(|candidate| (similarity(input, candidate), candidate))
        .filter(|(ratio, _)| *ratio >= 0.6)
        .collect();
    ranked.sort_by(|a, b| b.partial_cmp(a).unwrap());
    ranked.truncate(3);
    let mut names: Vec<_> = ranked.into_iter().map(|(_, name)| repr(name)).collect();
    names.sort();
    match names.len() {
        0 => String::new(),
        1 => format!(" Did you mean {}?", names[0]),
        _ => format!(" (Did you mean one of: {}?)", names.join(", ")),
    }
}
fn short_option(option: &str) -> Option<char> {
    option.strip_prefix('-').filter(|name| !name.starts_with('-')).and_then(|name| name.chars().next())
}
fn similarity(a: &str, b: &str) -> f64 {
    let a: Vec<_> = a.chars().collect();
    let b: Vec<_> = b.chars().collect();
    2.0 * matching(&b, &a) as f64 / (a.len() + b.len()) as f64
}
fn matching(a: &[char], b: &[char]) -> usize {
    let (i, j, size) = longest_match(a, b);
    if size == 0 {
        return 0;
    }
    size + matching(&a[..i], &b[..j]) + matching(&a[i + size..], &b[j + size..])
}
fn longest_match(a: &[char], b: &[char]) -> (usize, usize, usize) {
    let mut previous = vec![0; b.len() + 1];
    let mut best = (0, 0, 0);
    for (i, character) in a.iter().enumerate() {
        let current = matching_row(*character, b, &previous);
        let (end, length) =
            current.iter().copied().enumerate().fold((0, 0), |best, entry| if entry.1 > best.1 { entry } else { best });
        if length > best.2 {
            best = (i + 1 - length, end - length, length);
        }
        previous = current;
    }
    best
}
fn matching_row(character: char, b: &[char], previous: &[usize]) -> Vec<usize> {
    std::iter::once(0)
        .chain(b.iter().enumerate().map(|(j, other)| if *other == character { previous[j] + 1 } else { 0 }))
        .collect()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn matches_click_command_and_unicode_suggestions() {
        assert_eq!(
            unknown_command("", "réports", &["check", "report"]).to_string(),
            "No such command 'réports'. Did you mean 'report'?"
        );
        assert_eq!(
            unknown_command("graph", "contexts", &["context", "source"]).to_string(),
            "No such command 'contexts'. Did you mean 'context'?"
        );
    }
    #[test]
    fn matches_click_option_suggestions() {
        assert_eq!(
            unknown("report", "--skip-save", (&["--folder", "--format"], &["--save"])).to_string(),
            "No such option '--skip-save'. Did you mean '--save'?"
        );
        assert_eq!(
            unknown("report", "--for", (&["--folder", "--format"], &[])).to_string(),
            "No such option '--for'. (Did you mean one of: '--f', '--folder', '--format'?)"
        );
    }
}
