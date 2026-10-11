from sqlalchemy.sql.expression import table as t, column as c
select(t(fragment, c(fragment, is_literal=True)))