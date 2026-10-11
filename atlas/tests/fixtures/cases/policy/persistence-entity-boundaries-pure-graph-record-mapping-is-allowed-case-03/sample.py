def ids(items):
    found = set()
    for item in items:
        found.add(item.get('id'))
    return found