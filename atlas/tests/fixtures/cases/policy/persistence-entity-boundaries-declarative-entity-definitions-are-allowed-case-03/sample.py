import sqlalchemy as sa
from sqlalchemy import orm as mapping
class Base(mapping.DeclarativeBase):
    pass
class Row(Base):
    __tablename__ = 'rows'
    id: mapping.Mapped[int] = mapping.mapped_column(sa.Integer, primary_key=True)
