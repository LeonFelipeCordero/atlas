from alembic import op
from sqlalchemy import text as expression
op.create_index('graph_nodes_name', 'graph_nodes', ['repository_id', expression('(SELECT name FROM repositories)')])