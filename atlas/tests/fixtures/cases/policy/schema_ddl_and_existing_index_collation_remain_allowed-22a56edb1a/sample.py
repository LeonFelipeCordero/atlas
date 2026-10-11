from alembic import op as schema
from sqlalchemy import Column, Text
schema.create_table('example', Column('name', Text))