"""SQLite engine, explicit Alembic migrations, and session lifecycle."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as SqliteConnection
from typing import Generator, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine as sqlalchemy_create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas.domain.repositories import RepositoryError

def default_database_path() -> Path:
    """Keep the shared database in user data, never in the analyzed repository."""
    if path := os.environ.get("DATABASE_PATH"):
        return Path(path).expanduser()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return data_home.expanduser() / "atlas/atlas.sqlite"


def create_engine(path: str | Path | None = None) -> Engine:
    target = (Path(path).expanduser() if path is not None else default_database_path()).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = sqlalchemy_create_engine(f"sqlite:///{target}")

    @event.listens_for(engine, "connect")
    def configure(connection: object, _record: object) -> None:
        cursor = cast(SqliteConnection, connection).cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


def migrate_database(path: str | Path | None = None) -> None:
    """Apply Alembic revisions to a database explicitly."""
    engine = create_engine(path)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode = WAL")
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
    """Own the session lifecycle and translate storage errors at the boundary."""
    engine = create_engine(path)
    try:
        with Session(engine) as session:
            yield session
    except SQLAlchemyError as error:
        raise RepositoryError(str(error), 500) from error
    finally:
        engine.dispose()


def main() -> None:
    if len(sys.argv) not in (2, 3) or sys.argv[1] != "migrate":
        raise SystemExit("Usage: python -m atlas.persistence.database migrate [PATH]")
    migrate_database(sys.argv[2] if len(sys.argv) == 3 else None)


if __name__ == "__main__":
    main()
