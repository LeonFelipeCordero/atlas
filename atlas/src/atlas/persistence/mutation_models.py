"""Mutation history has no cascading dependencies on replaceable graph records."""

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class MutationSessionRow(Base):
    __tablename__ = "mutation_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class MutationSourceRow(Base):
    __tablename__ = "mutation_sources"

    session_id: Mapped[str] = mapped_column(Text, ForeignKey("mutation_sessions.session_id"), primary_key=True)
    path: Mapped[str] = mapped_column(Text, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class MutationSiteRow(Base):
    __tablename__ = "mutation_sites"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    site_id: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["session_id", "path"], ["mutation_sources.session_id", "mutation_sources.path"]),
    )


class MutationTrialRow(Base):
    __tablename__ = "mutation_trials"

    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    site_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("trial_id"),
        ForeignKeyConstraint(["session_id", "site_id"], ["mutation_sites.session_id", "mutation_sites.site_id"]),
    )
