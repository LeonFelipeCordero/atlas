class Row:
    def save(self, connection):
        connection.execute('SELECT 1')