class Service:
    def expose(self):
        return getattr(self, '_repository')