def describe(x):
    text = "literal x > 100 and x < 200"
    return f"literal x > 99: {x > 0}, {'yes' if x < 10 and x != 3 else 'no'}"
