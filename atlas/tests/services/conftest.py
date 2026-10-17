"""Real migrated SQLite, with exclusive suite access even under pytest-xdist."""

import fcntl
import hashlib
import tempfile
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
    return tmp_path_factory.mktemp("service-database") / "atlas.sqlite"


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
    identity = hashlib.sha256(str(Path(__file__).resolve()).encode()).hexdigest()[:16]
    lock = Path(tempfile.gettempdir()) / f"atlas-service-tests-{identity}.lock"
    # Hold the OS lock through setup, test, and teardown. Worker crashes release it.
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            migrate_database(_database_path)
            clean_database(_database_path)
            try:
                yield _database_path
            finally:
                clean_database(_database_path)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
