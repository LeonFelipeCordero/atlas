class Service:
    def expose(self):
        return {'repo': self._repository}