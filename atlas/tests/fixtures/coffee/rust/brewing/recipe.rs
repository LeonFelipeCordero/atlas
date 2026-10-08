use crate::report;

pub fn portions(name: &str) -> i32 {
    match name {
        "espresso" => 2,
        "filter" => 3,
        _ => 0,
    }
}

pub fn preview(name: &str) -> String {
    report::render(&[name])
}
