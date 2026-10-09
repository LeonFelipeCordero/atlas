"""SQLAlchemy models for registered repositories and their latest graphs."""

from sqlalchemy import ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("repositories_name_unique", func.lower(name), unique=True),)


class RepositoryGraphRow(Base):
    __tablename__ = "repository_graphs"

    repository_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    artifact: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[int] = mapped_column(Integer, nullable=False)
