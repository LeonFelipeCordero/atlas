"""SQLite migration and repository service regression tests."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from atlas.bootstrap import repository_service
from atlas.domain.repositories import RepositoryError
from atlas.persistence.database import (
    create_engine,
    default_database_path,
    migrate_database,
)
from sqlalchemy import text


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "db.sqlite"
    migrate_database(path)
    return path


def test_fresh_migration_repeated_downgrade_and_constraints(tmp_path: Path) -> None:
    path = tmp_path / "nested/db.sqlite"
    migrate_database(path)
    migrate_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001_initial",)
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall() == [
            ("alembic_version",), ("repositories",), ("repository_graphs",),
        ]
        assert db.execute("PRAGMA table_info('repositories')").fetchall() == [
            (0, "id", "TEXT", 1, None, 1),
            (1, "name", "TEXT", 1, None, 0),
            (2, "location", "TEXT", 1, None, 0),
            (3, "created_at", "INTEGER", 1, None, 0),
        ]
        assert db.execute("PRAGMA table_info('repository_graphs')").fetchall() == [
            (0, "repository_id", "TEXT", 1, None, 1),
            (1, "artifact", "TEXT", 1, None, 0),
            (2, "imported_at", "INTEGER", 1, None, 0),
        ]
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("INSERT INTO repositories VALUES ('a', 'Mixed', '.', 1)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO repositories VALUES ('b', 'MIXED', '.', 2)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO repository_graphs VALUES ('unknown', '{}', 1)")
        db.execute("INSERT INTO repository_graphs VALUES ('a', '{}', 1)")
        db.execute("DELETE FROM repositories WHERE id='a'")
        assert db.execute("SELECT count(*) FROM repository_graphs").fetchone() == (0,)
    engine = create_engine(path)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
            assert not connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='repositories'").scalar()
    finally:
        engine.dispose()
    migrate_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001_initial",)


def test_service_requires_explicit_migration(tmp_path: Path) -> None:
    path = tmp_path / "unmigrated.sqlite"
    with repository_service(path) as service:
        with pytest.raises(Exception, match="no such table"):
            service.list()
    migrate_database(path)
    with repository_service(path) as service:
        assert service.list() == []


def test_service_reindex_resolves_name_and_rolls_back_failed_write(database: Path, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_text("def run():\n    return 1\n")
    with repository_service(database) as service:
        first = service.register({"name": "  First ", "location": "source"})
        assert service.get_architecture(first.id) is None
        graph = service.index(first.name, root)
        assert graph.repositoryId == first.id
        assert graph.artifact["schemaVersion"] == 2
        with pytest.raises(RepositoryError) as duplicate:
            service.register({"name": "FIRST", "location": "elsewhere"})
        assert duplicate.value.status == 409
        replacement = service.index("fIrSt", root)
        assert replacement.repositoryId == first.id
        assert service.get_architecture(first.id) == replacement
        assert service.list()[0].importedAt == replacement.importedAt
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TRIGGER reject_graph BEFORE UPDATE ON repository_graphs
            BEGIN SELECT RAISE(ABORT, 'forced write failure'); END""")
    with repository_service(database) as service:
        original = service.get_architecture(first.id)
        with pytest.raises(Exception, match="forced write failure"):
            service.index("FIRST", root)
        assert service.get_architecture(first.id) == original
        with pytest.raises(ValueError):
            service.index(first.name, root / "missing")
        assert service.get_architecture(first.id) == original
        with pytest.raises(RepositoryError) as missing:
            service.index("absent", root)
        assert missing.value.status == 404


def test_non_ascii_name_resolution_matches_sqlite_lower(database: Path, tmp_path: Path) -> None:
    with repository_service(database) as service:
        registered = service.register({"name": "École", "location": "."})
        assert service.index("ÉCOLE", tmp_path).repositoryId == registered.id
        with pytest.raises(RepositoryError) as missing:
            service.index("école", tmp_path)
        assert missing.value.status == 404


def test_service_validation_and_shared_graph(database: Path, tmp_path: Path) -> None:
    with repository_service(database) as service:
        assert service.list() == []
        for invalid in ({}, None, {"name": " ", "location": "."}):
            with pytest.raises(RepositoryError) as error:
                service.register(invalid)
            assert error.value.status == 400
        repository = service.register({"name": "App", "location": "local"})
        assert repository.importedAt is None
        assert service.list() == [repository]
        assert service.get_architecture(repository.id) is None
        with pytest.raises(RepositoryError) as duplicate:
            service.register({"name": "aPP", "location": "x"})
        assert duplicate.value.status == 409
        for identifier, status in (("", 400), ("unknown", 404)):
            with pytest.raises(RepositoryError) as error:
                service.get_architecture(identifier)
            assert error.value.status == status
        graph = service.index(repository.name, tmp_path)
    with repository_service(database) as service:
        assert service.get_architecture(repository.id) == graph


def test_default_path_is_independent_of_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert default_database_path() == Path.home() / ".local/share/atlas/atlas.sqlite"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
    assert default_database_path() == tmp_path / "user-data/atlas/atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "selected.sqlite"))
    assert default_database_path() == tmp_path / "selected.sqlite"
