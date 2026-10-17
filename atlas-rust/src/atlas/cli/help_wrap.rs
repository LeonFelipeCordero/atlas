use regex::Regex;
use std::sync::LazyLock;
static CHUNKS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+|[^\s]+").unwrap());

pub fn wrap(text: &str, width: usize) -> Vec<String> {
    let mut lines = vec![];
    let mut current = String::new();
    let mut whitespace = String::new();
    for chunk in CHUNKS.find_iter(text).flat_map(|m| hyphen_chunks(m.as_str())) {
        if chunk.chars().all(char::is_whitespace) {
            whitespace.push_str(chunk);
            continue;
        }
        if !current.is_empty() && current.len() + whitespace.len() + chunk.len() > width {
            lines.push(std::mem::take(&mut current));
            whitespace.clear();
        }
        if !current.is_empty() {
            current.push_str(&whitespace);
        }
        whitespace.clear();
        current.push_str(chunk);
        split_long_line(&mut current, &mut lines, width);
    }
    if !current.is_empty() {
        lines.push(current);
    }
    lines
}
fn split_long_line(current: &mut String, lines: &mut Vec<String>, width: usize) {
    while current.len() > width {
        let end = current.char_indices().map(|(i, _)| i).take_while(|i| *i <= width).last().unwrap_or(width);
        let rest = current.split_off(end);
        lines.push(std::mem::replace(current, rest));
    }
}
fn hyphen_chunks(word: &str) -> Vec<&str> {
    let mut start = 0;
    let mut chunks = vec![];
    for (index, _) in word.match_indices('-') {
        if can_break_hyphen(word.as_bytes(), index) {
            chunks.push(&word[start..index + 1]);
            start = index + 1;
        }
    }
    chunks.push(&word[start..]);
    chunks
}
fn can_break_hyphen(bytes: &[u8], index: usize) -> bool {
    index >= 2
        && index + 2 < bytes.len()
        && bytes[index - 2..index].iter().all(u8::is_ascii_alphabetic)
        && bytes[index + 1..index + 3].iter().all(u8::is_ascii_alphabetic)
}
pub fn short_help(text: &str, limit: usize) -> String {
    let words: Vec<_> = text.split("\n\n").next().unwrap_or("").split_whitespace().collect();
    let mut chosen = Vec::new();
    let mut length = 0;
    for word in &words {
        let next = length + usize::from(!chosen.is_empty()) + word.len();
        if next > limit {
            return shortened(chosen, limit);
        }
        chosen.push(*word);
        length = next;
        if word.ends_with('.') {
            return chosen.join(" ");
        }
    }
    chosen.join(" ")
}
fn shortened(mut words: Vec<&str>, limit: usize) -> String {
    while words.join(" ").len() + 3 > limit {
        words.pop();
    }
    format!("{}...", words.join(" "))
}
