"""Service-owned composition: callers receive services, never repositories or sessions."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from atlas.persistence.database import migrate_database as _migrate_database
from atlas.persistence.navigation import navigation_reader as _navigation_reader
from atlas.persistence.repositories import repository_store as _repository_store
from .navigation import NavigationService
from .repositories import RepositoryService


@contextmanager
def navigation_service(project: str | None = None, revision: str | None = None, path: str | Path | None = None) -> Generator[NavigationService, None, None]:
    """Yield navigation inside one read-only snapshot at the supplied/default DB.

    Select project by ID/name, or nearest project containing cwd when omitted.
    Raise NavigationError for missing/ambiguous projects or stale revisions.
    Close the snapshot on exit; never create or migrate a database.
    """
    with _navigation_reader(Path.cwd() if project is None else project, revision, path) as reader:
        yield NavigationService(reader)


def migrate_database(path: str | Path | None = None) -> None:
    """Apply and commit all migrations at the supplied/default database path.

    Enable WAL; storage failures raise RepositoryError (500). No indexing runs.
    """
    _migrate_database(path)


@contextmanager
def repository_service(path: str | Path | None = None) -> Generator[RepositoryService, None, None]:
    """Yield a repository service with a managed session; never migrate implicitly.

    Use the supplied/default database path. Writes commit in store methods,
    not on context exit; cleanup rolls back pending work and closes storage.
    """
    with _repository_store(path) as repository:
        yield RepositoryService(repository)
