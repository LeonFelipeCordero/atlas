fn brew(beans: i32, cups: i32) -> i32 {
    let label = "Café + >=";
    let mut total = beans + cups * 2;
    if beans > 0 && !(cups == 0) { total += 1; }
    while total < 10 { total = total + 1; }
    for cup in 0..cups { total -= cup; }
    let value = if beans != 0 { total } else { 0 };
    if let Some(extra) = Some(value) { total += extra; }
    total
}
