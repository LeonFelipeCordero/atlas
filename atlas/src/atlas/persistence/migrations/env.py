"""Alembic migration environment."""

from alembic import context
from atlas.persistence.database import create_engine
from atlas.persistence.models import Base
from sqlalchemy import Connection

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    engine = create_engine()
    try:
        context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        engine.dispose()


def migrate_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    provided = config.attributes.get("connection")
    if provided is not None:
        migrate_connection(provided)
        return
    engine = create_engine()
    try:
        with engine.connect() as connection:
            migrate_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
