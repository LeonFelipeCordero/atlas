from atlas.domain.navigation import NavigationReader as Port
class Service:
    def __init__(self, r: Port):
        self._reader = r
        self.public = r