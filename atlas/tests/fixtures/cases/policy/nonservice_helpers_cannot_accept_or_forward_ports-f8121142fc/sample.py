from atlas.domain.repositories import RepositoryProtocol as Port
def outside(r: Port):
    return r.list()