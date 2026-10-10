"""Fresh write transactions and atomic normalized graph writes."""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from atlas.persistence.database import migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore as RuntimeRepositoryStore

from .graph_storage_fixture import (
    HEAD,
    graph_artifact,
    normalized_rows,
)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "transactions.sqlite"
    migrate_database(path)
    return path


def header(path: Path, identifier: str) -> tuple[Any, ...]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM repository_graphs WHERE repository_id=?", (identifier,)
        ).fetchone()
    assert row is not None
    return row


def replacement() -> dict[str, Any]:
    artifact = graph_artifact()
    artifact["repository"]["name"] = "Replacement root"
    artifact["schemaVersion"] = 3
    artifact["nodes"] = [artifact["nodes"][-1]]
    artifact["edges"] = []
    artifact["diagnostics"] = []
    return artifact


def assert_integrity(path: Path, revision: str = HEAD) -> None:
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (revision,)


def assert_replaced(path: Path, identifier: str, previous_revision: str) -> None:
    artifact = replacement()
    current = header(path, identifier)
    rows = normalized_rows(path, identifier)
    assert current[3] != previous_revision
    assert current[4:] == (3, artifact["repository"]["indexedAt"], "Replacement root", "/unavailable")
    assert json.loads(current[1]) == artifact
    assert len(rows.pop("graph_nodes")) == 1
    assert not any(rows.values())


def assert_new_graph(
    path: Path, identifier: str, expected_rows: dict[str, list[tuple[Any, ...]]]
) -> None:
    current = header(path, identifier)
    assert json.loads(current[1]) == graph_artifact()
    assert current[3] is not None
    expected = {
        table: [(identifier, *row[1:]) for row in records]
        for table, records in expected_rows.items()
    }
    assert normalized_rows(path, identifier) == expected


@pytest.mark.parametrize("operation", ["save", "save_new", "register"])
def test_public_write_ends_stale_orchestration_read(database: Path, operation: str) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        identifier = store.save_new("First", ".", graph_artifact()).repositoryId
        old_header = header(database, identifier)
        old_rows = normalized_rows(database, identifier)
        if operation == "save":
            assert store.resolve("First") == identifier
        else:
            assert [repository.name for repository in store.list()] == ["First"]
        assert session.in_transaction()
        with repository_session(database) as other_session:
            other_store = RuntimeRepositoryStore(other_session)
            other = other_store.register("Other", ".")
        assert store.resolve("Other") is None  # The read still owns the old WAL snapshot.
        if operation == "save":
            store.save(identifier, replacement())
            assert_replaced(database, identifier, old_header[3])
        elif operation == "save_new":
            created = store.save_new("New", ".", graph_artifact())
            assert created.artifact == graph_artifact()
            assert_new_graph(database, created.repositoryId, old_rows)
        else:
            created_repository = store.register("New", ".")
            assert store.resolve("New") == created_repository.id
            assert store.graph(created_repository.id) is None
        assert store.resolve("Other") == other.id
        if operation != "save":
            assert header(database, identifier) == old_header
            assert normalized_rows(database, identifier) == old_rows
    assert_integrity(database)


@pytest.mark.parametrize("operation", ["save", "save_new"])
@pytest.mark.parametrize("failure", ["serialization", "late_insert"])
def test_write_failure_is_atomic_and_same_session_reusable(
    database: Path, operation: str, failure: str
) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        identifier = store.save_new("First", ".", graph_artifact()).repositoryId
        before = (header(database, identifier), normalized_rows(database, identifier))
        artifact = graph_artifact()
        artifact["repository"]["name"] = "Uncommitted root"
        artifact["nodes"][0]["properties"]["lineCount"] = 99
        if failure == "serialization":
            artifact["future"] = {1, 2}
        else:
            with sqlite3.connect(database) as connection:
                connection.execute("""
                    CREATE TRIGGER fail_diagnostics BEFORE INSERT ON graph_diagnostics
                    BEGIN SELECT RAISE(ABORT, 'late graph insert failure'); END
                """)
        assert store.resolve("First") == identifier
        with pytest.raises(Exception, match="serializable|late graph insert failure"):
            if operation == "save":
                store.save(identifier, artifact)
            else:
                store.save_new("Ghost", ".", artifact)
        assert not session.new
        assert (header(database, identifier), normalized_rows(database, identifier)) == before
        assert store.resolve("Ghost") is None
        graph = store.graph(identifier)
        assert graph is not None and graph.artifact == graph_artifact()
        recovered = store.save_new("Recovered", ".", replacement())
        store.save(identifier, replacement())
        assert store.resolve("Recovered") == recovered.repositoryId
        assert {repository.name for repository in store.list()} == {"First", "Recovered"}
    assert_integrity(database)

