class Row:
    def load(self, session):
        return session.query(Row)