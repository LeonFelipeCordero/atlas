"""Literal schema expectations independent of ORM/application metadata."""

import sqlite3
from pathlib import Path

import pytest

from atlas.persistence.database import migrate_database

# type, NOT NULL, primary-key position (SQLite PRAGMA table_info).
SCHEMA = {
    "repositories": {
        "id": ("TEXT", 1, 1), "name": ("TEXT", 1, 0),
        "location": ("TEXT", 1, 0), "created_at": ("INTEGER", 1, 0),
    },
    "repository_graphs": {
        "repository_id": ("TEXT", 1, 1),
        "imported_at": ("INTEGER", 1, 0), "graph_revision": ("TEXT", 0, 0),
        "schema_version": ("INTEGER", 0, 0), "indexed_at": ("TEXT", 0, 0),
        "root_name": ("TEXT", 0, 0), "root_path": ("TEXT", 0, 0),
    },
    "graph_nodes": {
        "repository_id": ("TEXT", 1, 1), "node_key": ("TEXT", 1, 2),
        "parent_key": ("TEXT", 0, 0), "ordinal": ("INTEGER", 1, 0),
        "type": ("TEXT", 1, 0), "kind": ("TEXT", 1, 0), "level": ("TEXT", 1, 0),
        "name": ("TEXT", 1, 0), "language": ("TEXT", 0, 0),
        "qualified_name": ("TEXT", 0, 0), "path": ("TEXT", 0, 0),
    },
    "graph_files": {
        "repository_id": ("TEXT", 1, 1), "node_key": ("TEXT", 1, 2),
        "byte_count": ("INTEGER", 0, 0), "sha256": ("TEXT", 0, 0),
    },
    "graph_mutation_candidates": {
        "repository_id": ("TEXT", 1, 1), "candidate_id": ("TEXT", 1, 2),
        "file_key": ("TEXT", 1, 0), "ordinal": ("INTEGER", 1, 0),
        "path": ("TEXT", 1, 0), "language": ("TEXT", 1, 0),
        "source_hash": ("TEXT", 1, 0), "kind": ("TEXT", 1, 0),
        "operator": ("TEXT", 0, 0), "payload": ("TEXT", 1, 0),
    },
    "graph_symbols": {
        "repository_id": ("TEXT", 1, 1), "node_key": ("TEXT", 1, 2),
        "start_line": ("INTEGER", 0, 0), "start_column": ("INTEGER", 0, 0),
        "end_line": ("INTEGER", 0, 0), "end_column": ("INTEGER", 0, 0),
        "signature": ("TEXT", 0, 0), "visibility": ("TEXT", 0, 0),
    },
    "graph_node_metrics": {
        "repository_id": ("TEXT", 1, 1), "node_key": ("TEXT", 1, 2),
        "line_count": ("INTEGER", 0, 0), "parameter_count": ("INTEGER", 0, 0),
        "base_complexity": ("INTEGER", 0, 0), "nested_complexity": ("INTEGER", 0, 0),
        "loop_complexity": ("INTEGER", 0, 0), "total_complexity": ("INTEGER", 0, 0),
        "max_decision_depth": ("INTEGER", 0, 0),
    },
    "graph_node_decorators": {
        "repository_id": ("TEXT", 1, 1), "node_key": ("TEXT", 1, 2),
        "ordinal": ("INTEGER", 1, 3), "decorator": ("TEXT", 1, 0),
    },
    "graph_edges": {
        "repository_id": ("TEXT", 1, 1), "ordinal": ("INTEGER", 1, 2),
        "source_key": ("TEXT", 1, 0), "target_key": ("TEXT", 1, 0),
        "relationship": ("TEXT", 1, 0), "confidence": ("TEXT", 1, 0),
        "path": ("TEXT", 0, 0), "evidence": ("TEXT", 0, 0), "line": ("INTEGER", 0, 0),
        "type_only": ("BOOLEAN", 1, 0),
    },
    "graph_diagnostics": {
        "repository_id": ("TEXT", 1, 1), "ordinal": ("INTEGER", 1, 2),
        "severity": ("TEXT", 1, 0), "path": ("TEXT", 1, 0),
        "language": ("TEXT", 1, 0), "message": ("TEXT", 1, 0),
    },
}
FOREIGN_KEYS = {
    "repositories": [],
    "repository_graphs": [("repository_id", "repositories", "id", "CASCADE")],
    "graph_nodes": [
        ("repository_id", "repository_graphs", "repository_id", "CASCADE"),
        ("repository_id", "graph_nodes", "repository_id", "NO ACTION"),
        ("parent_key", "graph_nodes", "node_key", "NO ACTION"),
    ],
    "graph_files": [("repository_id", "graph_nodes", "repository_id", "CASCADE"), ("node_key", "graph_nodes", "node_key", "CASCADE")],
    "graph_mutation_candidates": [("repository_id", "graph_files", "repository_id", "CASCADE"), ("file_key", "graph_files", "node_key", "CASCADE")],
    "graph_symbols": [("repository_id", "graph_nodes", "repository_id", "CASCADE"), ("node_key", "graph_nodes", "node_key", "CASCADE")],
    "graph_node_metrics": [("repository_id", "graph_nodes", "repository_id", "CASCADE"), ("node_key", "graph_nodes", "node_key", "CASCADE")],
    "graph_node_decorators": [("repository_id", "graph_symbols", "repository_id", "CASCADE"), ("node_key", "graph_symbols", "node_key", "CASCADE")],
    "graph_edges": [
        ("repository_id", "repository_graphs", "repository_id", "CASCADE"),
        ("repository_id", "graph_nodes", "repository_id", "NO ACTION"),
        ("source_key", "graph_nodes", "node_key", "NO ACTION"),
        ("repository_id", "graph_nodes", "repository_id", "NO ACTION"),
        ("target_key", "graph_nodes", "node_key", "NO ACTION"),
    ],
    "graph_diagnostics": [("repository_id", "repository_graphs", "repository_id", "CASCADE")],
}
INDEXES = {
    "repositories": {"repositories_name_unique": (None,)},
    "repository_graphs": {},
    "graph_nodes": {
        "graph_nodes_parent": ("repository_id", "parent_key"),
        "graph_nodes_level": ("repository_id", "level"),
        "graph_nodes_name": ("repository_id", "name"),
        "graph_nodes_path": ("repository_id", "path"),
    },
    "graph_files": {}, "graph_symbols": {}, "graph_node_metrics": {}, "graph_node_decorators": {},
    "graph_edges": {
        "graph_edges_source": ("repository_id", "source_key", "relationship", "ordinal"),
        "graph_edges_target": ("repository_id", "target_key", "relationship", "ordinal"),
    },
    "graph_diagnostics": {"graph_diagnostics_path": ("repository_id", "path")},
    "graph_mutation_candidates": {"graph_mutation_candidates_file": ("repository_id", "file_key")},
}


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("graph-schema") / "schema.sqlite"
    migrate_database(path)
    return path


def test_exact_table_inventory_and_deferred_parentage(database: Path) -> None:
    with sqlite3.connect(database) as db:
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert {row[0] for row in tables} == {"alembic_version", *SCHEMA}
        ddl = db.execute("SELECT sql FROM sqlite_master WHERE name='graph_nodes'").fetchone()[0]
        assert "DEFERRABLE INITIALLY DEFERRED" in ddl
        assert "UNIQUE (repository_id, ordinal)" in ddl


@pytest.mark.parametrize("table", SCHEMA)
def test_exact_normalized_columns_and_foreign_keys(database: Path, table: str) -> None:
    with sqlite3.connect(database) as db:
        info = db.execute(f"PRAGMA table_info('{table}')").fetchall()
        assert {row[1]: (row[2], row[3], row[5]) for row in info} == SCHEMA[table]
        assert all(row[4] is None for row in info), "Missing measurements must not default to zero"
        keys = db.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
        assert sorted((row[3], row[2], row[4], row[6]) for row in keys) == sorted(FOREIGN_KEYS[table])
        assert all(row[5] == "NO ACTION" for row in keys)


def index_columns(db: sqlite3.Connection, name: str) -> tuple:
    return tuple(row[2] for row in db.execute(f"PRAGMA index_info('{name}')"))


@pytest.mark.parametrize("table", INDEXES)
def test_exact_scoped_indexes(database: Path, table: str) -> None:
    with sqlite3.connect(database) as db:
        actual = db.execute(f"PRAGMA index_list('{table}')").fetchall()
        assert {row[1]: index_columns(db, row[1]) for row in actual if row[3] == "c"} == INDEXES[table]
        assert all(row[2] == (row[1] == "repositories_name_unique") for row in actual if row[3] == "c")


def test_name_index_collation_and_registration_uniqueness(database: Path) -> None:
    with sqlite3.connect(database) as db:
        info = db.execute("PRAGMA index_xinfo('graph_nodes_name')").fetchall()
        assert next(row[4] for row in info if row[2] == "name") == "NOCASE"
        sql = db.execute("SELECT sql FROM sqlite_master WHERE name='repositories_name_unique'").fetchone()[0]
        assert "unique index" in sql.lower() and "lower(name)" in sql.lower()
