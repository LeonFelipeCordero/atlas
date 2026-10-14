"""Literal mutation schema and independent foreign keys, not ORM-derived baselines."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command

from atlas.persistence.database import create_engine, migrate_database
from tests.graph_storage_fixture import migration_config

SCHEMA = {
    "mutation_sessions": {"session_id": ("TEXT", 1, 1), "payload": ("TEXT", 1, 0)},
    "mutation_sources": {
        "session_id": ("TEXT", 1, 1), "path": ("TEXT", 1, 2),
        "ordinal": ("INTEGER", 1, 0), "payload": ("TEXT", 1, 0),
    },
    "mutation_sites": {
        "session_id": ("TEXT", 1, 1), "site_id": ("TEXT", 1, 2),
        "path": ("TEXT", 1, 0), "ordinal": ("INTEGER", 1, 0), "payload": ("TEXT", 1, 0),
    },
    "mutation_trials": {
        "ordinal": ("INTEGER", 1, 1), "trial_id": ("TEXT", 1, 0),
        "session_id": ("TEXT", 1, 0), "site_id": ("TEXT", 1, 0), "payload": ("TEXT", 1, 0),
    },
}
KEYS = {
    "mutation_sessions": [],
    "mutation_sources": [("session_id", "mutation_sessions", "session_id")],
    "mutation_sites": [("session_id", "mutation_sources", "session_id"), ("path", "mutation_sources", "path")],
    "mutation_trials": [("session_id", "mutation_sites", "session_id"), ("site_id", "mutation_sites", "site_id")],
}


@pytest.mark.parametrize("table", SCHEMA)
def test_exact_mutation_schema(tmp_path: Path, table: str) -> None:
    path = tmp_path / "db.sqlite"
    migrate_database(path)
    with sqlite3.connect(path) as db:
        info = db.execute(f"PRAGMA table_info('{table}')").fetchall()
        assert {row[1]: (row[2], row[3], row[5]) for row in info} == SCHEMA[table]
        keys = db.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
        assert sorted((row[3], row[2], row[4]) for row in keys) == sorted(KEYS[table])
        assert all(row[5:7] == ("NO ACTION", "NO ACTION") for row in keys)


def test_upgrade_from_previous_head_and_downgrade(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    engine = create_engine(path)
    config = migration_config()
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0004_drop_graph_artifact")
            connection.exec_driver_sql("INSERT INTO repositories VALUES ('old', 'Existing', '.', 1)")
        migrate_database(path)
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0004_drop_graph_artifact")
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT name FROM repositories").fetchall() == [("Existing",)]
            assert not {row[0] for row in db.execute("SELECT name FROM sqlite_master")} & set(SCHEMA)
    finally:
        engine.dispose()
