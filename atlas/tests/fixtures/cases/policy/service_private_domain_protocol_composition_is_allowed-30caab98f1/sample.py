from atlas.domain.repositories import RepositoryProtocol as Port
class Service:
    def __init__(self, repository: Port):
        self._repository = repository
    def data(self):
        return self._repository.list()
