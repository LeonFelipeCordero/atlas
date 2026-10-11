from atlas.domain.repositories import RepositoryProtocol as Port
class Service:
    def __init__(self, r: 'Port'):
        self._repository = r
        self.public = r