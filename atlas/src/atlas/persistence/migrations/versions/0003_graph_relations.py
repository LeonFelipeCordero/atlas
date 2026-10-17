"""Add graph metrics, decorators, edges, and diagnostics.

Revision ID: 0003_graph_relations
Revises: 0002_graph_nodes
"""

from alembic import op
from sqlalchemy import Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer, Text

revision = "0003_graph_relations"
down_revision = "0002_graph_nodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create metric, decorator, adjacency, and diagnostic tables/indexes.

    Do not backfill existing graphs or commit outside Alembic's transaction.
    """
    op.create_table(
        "graph_node_metrics",
        Column("repository_id", Text, primary_key=True, nullable=False),
        Column("node_key", Text, primary_key=True, nullable=False),
        Column("line_count", Integer, nullable=True),
        Column("parameter_count", Integer, nullable=True),
        Column("base_complexity", Integer, nullable=True),
        Column("nested_complexity", Integer, nullable=True),
        Column("loop_complexity", Integer, nullable=True),
        Column("total_complexity", Integer, nullable=True),
        Column("max_decision_depth", Integer, nullable=True),
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )
    op.create_table(
        "graph_node_decorators",
        Column("repository_id", Text, primary_key=True, nullable=False),
        Column("node_key", Text, primary_key=True, nullable=False),
        Column("ordinal", Integer, primary_key=True, nullable=False),
        Column("decorator", Text, nullable=False),
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_symbols.repository_id", "graph_symbols.node_key"], ondelete="CASCADE"),
    )
    op.create_table(
        "graph_edges",
        Column("repository_id", Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False),
        Column("ordinal", Integer, primary_key=True, nullable=False),
        Column("source_key", Text, nullable=False),
        Column("target_key", Text, nullable=False),
        Column("relationship", Text, nullable=False),
        Column("confidence", Text, nullable=False),
        Column("path", Text, nullable=True),
        Column("evidence", Text, nullable=True),
        Column("line", Integer, nullable=True),
        Column("type_only", Boolean, nullable=False),
        ForeignKeyConstraint(["repository_id", "source_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION"),
        ForeignKeyConstraint(["repository_id", "target_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION"),
    )
    op.create_index("graph_edges_source", "graph_edges", ["repository_id", "source_key", "relationship", "ordinal"])
    op.create_index("graph_edges_target", "graph_edges", ["repository_id", "target_key", "relationship", "ordinal"])
    op.create_table(
        "graph_diagnostics",
        Column("repository_id", Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False),
        Column("ordinal", Integer, primary_key=True, nullable=False),
        Column("severity", Text, nullable=False),
        Column("path", Text, nullable=False),
        Column("language", Text, nullable=False),
        Column("message", Text, nullable=False),
    )
    op.create_index("graph_diagnostics_path", "graph_diagnostics", ["repository_id", "path"])


def downgrade() -> None:
    """Discard relation, diagnostic, decorator, and metric data; retain nodes.

    Leave transaction control to Alembic.
    """
    op.drop_table("graph_diagnostics")
    op.drop_table("graph_edges")
    op.drop_table("graph_node_decorators")
    op.drop_table("graph_node_metrics")
