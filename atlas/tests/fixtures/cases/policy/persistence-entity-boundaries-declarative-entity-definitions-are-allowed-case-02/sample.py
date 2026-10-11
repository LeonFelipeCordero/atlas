from sqlalchemy import ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
class Base(DeclarativeBase):
    pass
class Row(Base):
    __tablename__ = 'rows'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_id: Mapped[str] = mapped_column(Text, ForeignKey('rows.id'))
    name: Mapped[str] = mapped_column(Text)
    __table_args__ = (Index('rows_name', func.lower(name), unique=True),)
