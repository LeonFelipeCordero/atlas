fun brew(beans: Int, cups: Int): Int {
    val label = "Café + >="
    var total = beans + cups * 2
    if (beans > 0 && !(cups == 0)) total += 1
    while (total < 10) total = total + 1
    for (cup in 0..cups) total -= cup
    return if (beans != 0) total else 0
}
