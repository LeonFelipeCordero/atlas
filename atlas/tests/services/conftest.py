"""Real migrated SQLite, isolated per pytest worker and cleaned after each test."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from atlas.persistence.database import create_engine
from atlas.persistence.models import Base, RepositoryRow
from atlas.services.factories import migrate_database


@pytest.fixture(scope="session")
def _database_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # A private file per worker also isolates concurrent pytest invocations.
    path = tmp_path_factory.mktemp("service-database") / ".local" / "share" / "atlas" / "atlas.sqlite"
    migrate_database(path)
    return path


def clean_database(path: Path) -> None:
    engine = create_engine(path)
    try:
        with engine.begin() as connection:
            connection.execute(delete(RepositoryRow))
            # Cascades must clear every graph table, not just registrations.
            for table in Base.metadata.sorted_tables:
                assert connection.scalar(select(func.count()).select_from(table)) == 0
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def database(_database_path: Path) -> Iterator[Path]:
    try:
        yield _database_path
    finally:
        clean_database(_database_path)
