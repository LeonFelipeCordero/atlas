"""Persist mutation candidates owned by the latest graph's files.

Revision ID: 0005_mutation_candidates
Revises: 0004_drop_graph_artifact
"""

from alembic import op
from sqlalchemy import Column, ForeignKeyConstraint, Integer, Text

revision = "0005_mutation_candidates"
down_revision = "0004_drop_graph_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create file-owned mutation storage/index without generating candidates.

    Leave transaction control to Alembic; reindex to populate saved candidates.
    """
    op.create_table(
        "graph_mutation_candidates",
        Column("repository_id", Text, primary_key=True, nullable=False),
        Column("candidate_id", Text, primary_key=True, nullable=False),
        Column("file_key", Text, nullable=False),
        Column("ordinal", Integer, nullable=False),
        Column("path", Text, nullable=False),
        Column("language", Text, nullable=False),
        Column("source_hash", Text, nullable=False),
        Column("kind", Text, nullable=False),
        Column("operator", Text, nullable=True),
        Column("payload", Text, nullable=False),
        ForeignKeyConstraint(["repository_id", "file_key"], ["graph_files.repository_id", "graph_files.node_key"], ondelete="CASCADE"),
    )
    op.create_index("graph_mutation_candidates_file", "graph_mutation_candidates", ["repository_id", "file_key"])


def downgrade() -> None:
    """Discard saved mutation candidates while retaining graph files.

    Leave transaction control to Alembic.
    """
    op.drop_table("graph_mutation_candidates")
