from sqlalchemy import select, column
session.execute(select(column('(SELECT name FROM repositories LIMIT 1)', is_literal=True)))