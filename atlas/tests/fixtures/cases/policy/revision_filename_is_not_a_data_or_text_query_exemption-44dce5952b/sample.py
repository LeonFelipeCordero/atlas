from alembic import op as migration
write = migration.execute
write(statement)