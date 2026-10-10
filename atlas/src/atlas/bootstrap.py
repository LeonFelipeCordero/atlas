"""Composition root for CLI services and explicit database migrations."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from atlas.persistence.database import migrate_database as _migrate_database
from atlas.persistence.database import repository_session
from atlas.persistence.repositories import RepositoryStore
from atlas.services.repositories import RepositoryService
from atlas.persistence.navigation import navigation_reader
from atlas.services.navigation import NavigationService


@contextmanager
def navigation_service(project: str, revision: str | None = None, path: str | Path | None = None) -> Generator[NavigationService, None, None]:
    """Compose navigation inside one explicit read-only snapshot."""
    with navigation_reader(project, revision, path) as reader:
        yield NavigationService(reader)


def migrate_database(path: str | Path | None = None) -> None:
    """Apply migrations without exposing persistence imports to the CLI."""
    _migrate_database(path)


@contextmanager
def repository_service(path: str | Path | None = None) -> Generator[RepositoryService, None, None]:
    """Construct a service backed by one session; never migrate implicitly."""
    with repository_session(path) as session:
        yield RepositoryService(RepositoryStore(session))
