class Service:
    def expose(self):
        dependency = {'repo': self._repository}
        return dependency