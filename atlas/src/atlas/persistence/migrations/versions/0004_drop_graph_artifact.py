"""Remove the transitional whole-graph JSON blob without backfilling."""

from alembic import op
from sqlalchemy import Column, Text

revision = "0004_drop_graph_artifact"
down_revision = "0003_graph_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("repository_graphs", "artifact")


def downgrade() -> None:
    # Discarded JSON cannot be restored; old readers must reindex after downgrade.
    op.add_column("repository_graphs", Column("artifact", Text, nullable=False, server_default="{}"))
