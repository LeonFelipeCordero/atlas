from sqlalchemy import text as sql
session.execute(sql('SELECT * FROM repositories'))