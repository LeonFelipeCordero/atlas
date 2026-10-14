"""Add independent immutable mutation sessions and append-only experiment trials."""

from alembic import op
from sqlalchemy import Column, ForeignKeyConstraint, Integer, Text, UniqueConstraint

revision = "0005_mutation_ledger"
down_revision = "0004_drop_graph_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mutation_sessions",
        Column("session_id", Text, primary_key=True, nullable=False),
        Column("payload", Text, nullable=False),
    )
    op.create_table(
        "mutation_sources",
        Column("session_id", Text, primary_key=True, nullable=False),
        Column("path", Text, primary_key=True, nullable=False),
        Column("ordinal", Integer, nullable=False),
        Column("payload", Text, nullable=False),
        ForeignKeyConstraint(["session_id"], ["mutation_sessions.session_id"]),
    )
    op.create_table(
        "mutation_sites",
        Column("session_id", Text, primary_key=True, nullable=False),
        Column("site_id", Text, primary_key=True, nullable=False),
        Column("path", Text, nullable=False),
        Column("ordinal", Integer, nullable=False),
        Column("payload", Text, nullable=False),
        ForeignKeyConstraint(["session_id", "path"], ["mutation_sources.session_id", "mutation_sources.path"]),
    )
    op.create_table(
        "mutation_trials",
        Column("ordinal", Integer, primary_key=True, autoincrement=True, nullable=False),
        Column("trial_id", Text, nullable=False),
        Column("session_id", Text, nullable=False),
        Column("site_id", Text, nullable=False),
        Column("payload", Text, nullable=False),
        UniqueConstraint("trial_id"),
        ForeignKeyConstraint(["session_id", "site_id"], ["mutation_sites.session_id", "mutation_sites.site_id"]),
    )


def downgrade() -> None:
    op.drop_table("mutation_trials")
    op.drop_table("mutation_sites")
    op.drop_table("mutation_sources")
    op.drop_table("mutation_sessions")
