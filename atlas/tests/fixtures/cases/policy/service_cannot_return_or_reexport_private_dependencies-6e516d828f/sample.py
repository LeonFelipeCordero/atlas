class Service:
    def expose(self):
        return foreign_helper(self._repository)