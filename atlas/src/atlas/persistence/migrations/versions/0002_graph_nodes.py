"""Add graph metadata, nodes, files, and symbols.

Revision ID: 0002_graph_nodes
Revises: 0001_initial
"""

from alembic import op
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint, text

revision = "0002_graph_nodes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repository_graphs", Column("graph_revision", Text, nullable=True))
    op.add_column("repository_graphs", Column("schema_version", Integer, nullable=True))
    op.add_column("repository_graphs", Column("indexed_at", Text, nullable=True))
    op.add_column("repository_graphs", Column("root_name", Text, nullable=True))
    op.add_column("repository_graphs", Column("root_path", Text, nullable=True))
    op.create_table(
        "graph_nodes",
        Column("repository_id", Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False),
        Column("node_key", Text, primary_key=True, nullable=False),
        Column("parent_key", Text, nullable=True),
        Column("ordinal", Integer, nullable=False),
        Column("type", Text, nullable=False),
        Column("kind", Text, nullable=False),
        Column("level", Text, nullable=False),
        Column("name", Text, nullable=False),
        Column("language", Text, nullable=True),
        Column("qualified_name", Text, nullable=True),
        Column("path", Text, nullable=True),
        UniqueConstraint("repository_id", "ordinal"),
        ForeignKeyConstraint(["repository_id", "parent_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
    )
    op.create_index("graph_nodes_parent", "graph_nodes", ["repository_id", "parent_key"])
    op.create_index("graph_nodes_level", "graph_nodes", ["repository_id", "level"])
    op.create_index("graph_nodes_name", "graph_nodes", ["repository_id", text("name COLLATE NOCASE")])
    op.create_index("graph_nodes_path", "graph_nodes", ["repository_id", "path"])
    op.create_table(
        "graph_files",
        Column("repository_id", Text, primary_key=True, nullable=False),
        Column("node_key", Text, primary_key=True, nullable=False),
        Column("byte_count", Integer, nullable=True),
        Column("sha256", Text, nullable=True),
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )
    op.create_table(
        "graph_symbols",
        Column("repository_id", Text, primary_key=True, nullable=False),
        Column("node_key", Text, primary_key=True, nullable=False),
        Column("start_line", Integer, nullable=True),
        Column("start_column", Integer, nullable=True),
        Column("end_line", Integer, nullable=True),
        Column("end_column", Integer, nullable=True),
        Column("signature", Text, nullable=True),
        Column("visibility", Text, nullable=True),
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("graph_symbols")
    op.drop_table("graph_files")
    op.drop_table("graph_nodes")
    op.drop_column("repository_graphs", "root_path")
    op.drop_column("repository_graphs", "root_name")
    op.drop_column("repository_graphs", "indexed_at")
    op.drop_column("repository_graphs", "schema_version")
    op.drop_column("repository_graphs", "graph_revision")
