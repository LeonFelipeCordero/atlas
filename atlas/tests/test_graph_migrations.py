"""Schema upgrades do not decode old artifacts; failed DDL remains atomic."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from atlas.persistence.database import create_engine, migrate_database
from sqlalchemy import event

from .graph_storage_fixture import HEAD, migration_config, normalized_rows


def test_schema_upgrade_leaves_existing_artifacts_unparsed(tmp_path: Path) -> None:
    path = tmp_path / "existing.sqlite"
    engine = create_engine(path)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "0001_initial")
            connection.exec_driver_sql("INSERT INTO repositories VALUES ('old', 'Local', '.', 7)")
            connection.exec_driver_sql("INSERT INTO repository_graphs VALUES ('old', 'not JSON', 123)")
    finally:
        engine.dispose()
    migrate_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD,)
        assert db.execute("SELECT * FROM repositories").fetchall() == [("old", "Local", ".", 7)]
        assert db.execute("SELECT * FROM repository_graphs").fetchone() == (
            "old", 123, None, None, None, None, None,
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert not any(normalized_rows(path, "old").values())


def test_fresh_migration_late_failure_rolls_back_all_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "fresh.sqlite"
    engine = create_engine(path)

    @event.listens_for(engine, "before_cursor_execute")
    def fail_schema(*cursor_event):
        statement = cursor_event[2]
        if "CREATE TABLE graph_diagnostics" in statement:
            raise RuntimeError("forced schema failure")

    monkeypatch.setattr("atlas.persistence.database.create_engine", lambda _path: engine)
    with pytest.raises(RuntimeError, match="forced schema failure"):
        migrate_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
