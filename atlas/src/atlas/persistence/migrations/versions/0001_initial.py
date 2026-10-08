"""Initial repository and graph tables.

Revision ID: 0001_initial
Revises:
"""

from alembic import op
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, Text, func

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        Column("id", Text, primary_key=True, nullable=False),
        Column("name", Text, nullable=False),
        Column("location", Text, nullable=False),
        Column("created_at", Integer, nullable=False),
    )
    repositories = Table("repositories", MetaData(), Column("name", Text))
    op.create_index("repositories_name_unique", "repositories", [func.lower(repositories.c.name)], unique=True)
    op.create_table(
        "repository_graphs",
        Column("repository_id", Text, ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        Column("artifact", Text, nullable=False),
        Column("imported_at", Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("repository_graphs")
    op.drop_index("repositories_name_unique", table_name="repositories")
    op.drop_table("repositories")
