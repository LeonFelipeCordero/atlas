from atlas.persistence.navigation import navigation_reader as _reader
def factory():
    with _reader('p') as reader:
        dependency = {'reader': reader}
        return dependency