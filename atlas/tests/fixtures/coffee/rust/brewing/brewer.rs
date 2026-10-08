#[path = "recipe.rs"]
mod recipe;
#[path = "../reporting/report.rs"]
mod report;

pub fn brew(names: &[&str]) -> String {
    if names.is_empty() {
        return report::render(&[]);
    }
    let valid: Vec<&str> = names.iter().copied()
        .filter(|name| recipe::portions(name) > 0).collect();
    report::render(&valid)
}

pub fn retry(attempts: i32) -> i32 {
    if attempts <= 0 {
        return 0;
    }
    1 + retry(attempts - 1)
}

pub fn score(batches: &[Vec<&str>]) -> i32 {
    let mut result = 0;
    for batch in batches {
        for name in batch {
            let count = recipe::portions(name);
            if count > 0 && count <= 3 {
                result += count;
            }
        }
    }
    result
}

fn main() {
    println!("{}", brew(&["espresso", "filter", "invalid"]));
}
