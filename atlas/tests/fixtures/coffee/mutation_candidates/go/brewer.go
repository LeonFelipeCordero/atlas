package coffee

func brew(beans int, cups int) int {
    label := "Café + >="
    _ = label
    total := beans + cups * 2
    if beans > 0 && !(cups == 0) { total += 1 }
    for total < 10 { total = total + 1 }
    for cup := 0; cup < cups; cup += 1 { total -= cup }
    for _, cup := range []int{1, 2} { total -= cup }
    return total
}
