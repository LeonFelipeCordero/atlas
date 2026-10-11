from atlas.domain.navigation import NavigationReader as Port
class Service:
    def __init__(self, reader: Port):
        self._reader = reader
    def data(self):
        return self._reader.overview()
