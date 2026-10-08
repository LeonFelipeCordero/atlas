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

// Deliberately exceed the cyclomatic-complexity limit without deep nesting.
pub fn classify(amount: i32) -> i32 {
    let mut category = 0;
    if amount > 0 { category += 1; }
    if amount > 1 { category += 1; }
    if amount > 2 { category += 1; }
    if amount > 3 { category += 1; }
    if amount > 4 { category += 1; }
    if amount > 5 { category += 1; }
    if amount > 6 { category += 1; }
    if amount > 7 { category += 1; }
    category
}

// Deliberately exceed the decision-nesting limit without loops.
pub fn ready(water: i32, beans: i32, cups: i32, temperature: i32) -> bool {
    if water > 0 {
        if beans > 0 {
            if cups > 0 {
                if temperature > 0 {
                    return true;
                }
            }
        }
    }
    false
}

fn main() {
    println!("{}", brew(&["espresso", "filter", "invalid"]));
}
