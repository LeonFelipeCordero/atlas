"""Composition exposes services and domain errors, never storage-specific errors."""

from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from atlas.bootstrap import migrate_database, repository_service
from atlas.domain.repositories import RepositoryError
from atlas.persistence import database


def test_service_does_not_migrate_and_disposes_on_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = database.create_engine(tmp_path / "unmigrated.sqlite")
    disposed = []
    event.listen(engine, "engine_disposed", lambda _: disposed.append(True))
    monkeypatch.setattr(database, "create_engine", lambda path: engine)

    with pytest.raises(RepositoryError, match="no such table") as caught:
        with repository_service(tmp_path / "unmigrated.sqlite") as service:
            service.list()

    assert caught.value.status == 500
    assert isinstance(caught.value.__cause__, SQLAlchemyError)
    assert disposed == [True]


def test_service_preserves_domain_errors(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    migrate_database(path)
    error = RepositoryError("Invalid input", 400)
    with pytest.raises(RepositoryError) as caught:
        with repository_service(path):
            raise error
    assert caught.value is error


def test_migration_translates_storage_error_and_disposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = database.create_engine(tmp_path / "db.sqlite")
    disposed = []
    event.listen(engine, "engine_disposed", lambda _: disposed.append(True))
    monkeypatch.setattr(database, "create_engine", lambda path: engine)
    error = SQLAlchemyError("Migration failed")

    def fail_upgrade(*args: object) -> None:
        raise error

    monkeypatch.setattr(database.command, "upgrade", fail_upgrade)
    with pytest.raises(RepositoryError, match="Migration failed") as caught:
        migrate_database(tmp_path / "db.sqlite")

    assert caught.value.status == 500
    assert caught.value.__cause__ is error
    assert disposed == [True]
