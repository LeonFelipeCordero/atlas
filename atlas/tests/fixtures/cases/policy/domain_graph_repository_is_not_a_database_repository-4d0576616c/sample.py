from atlas.domain.models import ParsedRepository as Graph
class Index:
    def __init__(self, repository: Graph):
        self.repository = repository
    def files(self):
        return self.repository.files

    def bypass(self):
        return self.repository.execute(statement)