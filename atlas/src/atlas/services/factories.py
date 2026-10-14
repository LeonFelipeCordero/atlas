"""Service-owned composition: callers receive services, never repositories or sessions."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from atlas.persistence.database import migrate_database as _migrate_database
from atlas.persistence.navigation import navigation_reader as _navigation_reader
from atlas.persistence.repositories import repository_store as _repository_store
from atlas.persistence.mutation_repository import mutation_store as _mutation_store
from .mutation import MutationService
from .navigation import NavigationService
from .repositories import RepositoryService


@contextmanager
def navigation_service(project: str | None = None, revision: str | None = None, path: str | Path | None = None) -> Generator[NavigationService, None, None]:
    """Compose navigation inside one explicit read-only snapshot."""
    with _navigation_reader(Path.cwd() if project is None else project, revision, path) as reader:
        yield NavigationService(reader)


def migrate_database(path: str | Path | None = None) -> None:
    """Explicit schema administration through the service construction boundary."""
    _migrate_database(path)


@contextmanager
def mutation_service(path: str | Path | None = None) -> Generator[MutationService, None, None]:
    """Construct a ledger service without implicitly migrating the database."""
    with _mutation_store(path) as repository:
        yield MutationService(repository)


@contextmanager
def repository_service(path: str | Path | None = None) -> Generator[RepositoryService, None, None]:
    """Construct a service backed by a repository; never migrate implicitly."""
    with _repository_store(path) as repository:
        yield RepositoryService(repository)
