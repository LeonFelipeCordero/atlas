from atlas.persistence.repositories import repository_store as _store
def factory():
    with _store() as repository:
        yield repository