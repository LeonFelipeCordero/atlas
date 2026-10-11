from sqlalchemy import insert, delete
session.execute(insert(Row), records)
session.execute(delete(Row))