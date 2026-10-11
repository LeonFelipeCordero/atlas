class Service:
    def expose(self):
        dependency = self._repository
        return dependency