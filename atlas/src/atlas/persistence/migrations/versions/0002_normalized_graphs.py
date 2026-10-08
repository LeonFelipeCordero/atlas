"""Normalize existing and future graph snapshots for SQL analysis.

Revision ID: 0002_normalized_graphs
Revises: 0001_initial
"""

import json

from alembic import op
from sqlalchemy import text

from atlas.persistence.normalized import replace_graph
from atlas.persistence.normalized_schema import TABLES, metadata

revision = "0002_normalized_graphs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    metadata.create_all(connection, tables=TABLES)
    for identifier, payload in connection.execute(
        text("SELECT repository_id, artifact FROM repository_graphs")
    ):
        replace_graph(connection, identifier, json.loads(payload))


def downgrade() -> None:
    metadata.drop_all(op.get_bind(), tables=TABLES)
