def brew(beans, cups):
    """Café: strings like a + b and >= are not operators."""
    total = beans + cups * 2
    if beans > 0 and not cups == 0:
        total += 1
    while total < 10:
        total = total + 1
    for cup in cups:
        total -= cup
    return total if beans != 0 else 0
