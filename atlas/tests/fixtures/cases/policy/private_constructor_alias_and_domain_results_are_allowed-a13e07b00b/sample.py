from atlas.domain.repositories import RepositoryProtocol as Port
class Service:
    def __init__(self, r: Port):
        alias = r
        self._repository = alias
    def data(self):
        return self._repository.list()
