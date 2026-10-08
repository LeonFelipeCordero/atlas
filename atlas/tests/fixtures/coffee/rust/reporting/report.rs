use crate::recipe;

pub fn total(names: &[&str]) -> i32 {
    names.iter().map(|name| recipe::portions(name)).sum()
}

pub fn render(names: &[&str]) -> String {
    let entries: Vec<String> = names.iter()
        .map(|name| format!("{}={}", name, recipe::portions(name)))
        .collect();
    format!("coffee:{};total={}", entries.join(","), total(names))
}
