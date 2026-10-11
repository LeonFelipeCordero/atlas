from sqlalchemy.sql import quoted_name as name
Row.__table__.c.name.name = name(fragment, False)