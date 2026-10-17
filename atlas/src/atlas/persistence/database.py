"""SQLite engine, explicit Alembic migrations, and session lifecycle."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as SqliteConnection
from typing import Generator, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine as sqlalchemy_create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas.domain.repositories import RepositoryError

def default_database_path() -> Path:
    """Return DATABASE_PATH, or atlas/atlas.sqlite under XDG_DATA_HOME/user data.

    Expand home markers without creating the shared database or its directories.
    """
    if path := os.environ.get("DATABASE_PATH"):
        return Path(path).expanduser()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return data_home.expanduser() / "atlas/atlas.sqlite"


def create_engine(path: str | Path | None = None) -> Engine:
    """Return a SQLite engine with foreign keys and explicit transaction control.

    Resolve the supplied or default path and create its parent directories, but
    do not migrate. The caller must dispose the engine after use.
    """
    target = (Path(path).expanduser() if path is not None else default_database_path()).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = sqlalchemy_create_engine(f"sqlite:///{target}")

    @event.listens_for(engine, "connect")
    def configure(connection: object, _record: object) -> None:
        sqlite = cast(SqliteConnection, connection)
        # SQLAlchemy owns BEGIN, including transactional DDL and consistent reads.
        sqlite.isolation_level = None
        cursor = sqlite.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE" if connection.info.get("migrating") else "BEGIN")

    return engine


def migrate_database(path: str | Path | None = None) -> None:
    """Enable WAL and apply all Alembic revisions at the supplied/default path.

    Commit schema changes together; roll them back on failure. Translate
    SQLAlchemy failures to RepositoryError (500) and always dispose the engine.
    """
    engine = create_engine(path)
    try:
        with engine.connect() as connection:
            # journal_mode must change outside the migration transaction.
            sqlite = cast(SqliteConnection, connection.connection.driver_connection)
            sqlite.execute("PRAGMA journal_mode = WAL").close()
            connection.info["migrating"] = True
            with connection.begin():
                config = Config()
                config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
    except SQLAlchemyError as error:
        raise RepositoryError(str(error), 500) from error
    finally:
        engine.dispose()


@contextmanager
def repository_session(path: str | Path | None = None) -> Generator[Session, None, None]:
    """Yield a session at the supplied/default path without migrating or committing.

    Close the session and dispose the engine on exit; uncommitted work rolls
    back. Translate SQLAlchemy failures, including body errors, to
    RepositoryError (500). Store methods own explicit commits.
    """
    engine = create_engine(path)
    try:
        with Session(engine) as session:
            yield session
    except SQLAlchemyError as error:
        raise RepositoryError(str(error), 500) from error
    finally:
        engine.dispose()


def main() -> None:
    """Run explicit migration from argv; exit with usage for invalid arguments."""
    if len(sys.argv) not in (2, 3) or sys.argv[1] != "migrate":
        raise SystemExit("Usage: python -m atlas.persistence.database migrate [PATH]")
    migrate_database(sys.argv[2] if len(sys.argv) == 3 else None)


if __name__ == "__main__":
    main()
