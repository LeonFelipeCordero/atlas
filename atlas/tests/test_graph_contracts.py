"""Normalized writes handle missing/null metadata and reject ambiguous containers."""

import sqlite3
from pathlib import Path

import pytest
from atlas.persistence.database import migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore

from .graph_storage_fixture import graph_artifact, normalized_rows


def null_container_artifact(container: str) -> dict:
    artifact = graph_artifact()
    if container == "repository":
        artifact["repository"] = None
    elif container == "decorators":
        artifact["nodes"][0]["properties"]["decorators"] = None
    else:
        index = 0 if container == "callable_properties" else 2
        artifact["nodes"][index]["properties"] = None
    return artifact


@pytest.mark.parametrize("container", ["repository", "callable_properties", "file_properties", "decorators"])
def test_null_containers_round_trip(tmp_path: Path, container: str) -> None:
    path = tmp_path / "null.sqlite"
    artifact = null_container_artifact(container)
    migrate_database(path)
    with repository_session(path) as session:
        store = RepositoryStore(session)
        result = store.save_new("Nulls", ".", artifact)
        graph = store.graph(result.repositoryId)
        assert graph == result
        assert graph is not None and graph.stats.nodes == len(artifact["nodes"])
    with sqlite3.connect(path) as db:
        assert "artifact" not in [row[1] for row in db.execute("PRAGMA table_info(repository_graphs)")]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("artifact", [{}, {"repository": None}, {"nodes": [], "edges": [], "diagnostics": []}])
def test_missing_or_empty_collections_have_no_normalized_rows(tmp_path: Path, artifact: dict) -> None:
    path = tmp_path / "empty.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        result = RepositoryStore(session).save_new("Empty", ".", artifact)
    assert not any(normalized_rows(path, result.repositoryId).values())


def malformed_artifact(field: str, value) -> dict:
    artifact = graph_artifact()
    if field == "decorators":
        artifact["nodes"][0]["properties"][field] = value
    else:
        artifact[field] = value
    return artifact


INVALID_COLLECTIONS = [
    ("nodes", {"0": graph_artifact()["nodes"][0]}),
    ("edges", {"0": graph_artifact()["edges"][0]}),
    ("diagnostics", {"0": graph_artifact()["diagnostics"][0]}),
    ("decorators", {"0": "@trace", "1": "@audit"}),
    ("nodes", None), ("edges", None), ("diagnostics", None),
    ("nodes", "node"), ("edges", True), ("diagnostics", 1),
    ("decorators", "@trace"), ("decorators", True), ("decorators", 1),
]


@pytest.mark.parametrize("field,value", INVALID_COLLECTIONS)
def test_malformed_occurrence_containers_reject_without_changing_storage(tmp_path: Path, field: str, value) -> None:
    invalid = malformed_artifact(field, value)
    path = tmp_path / "live.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        store = RepositoryStore(session)
        identifier = store.save_new("Valid", ".", graph_artifact()).repositoryId
        before = normalized_rows(path, identifier)
        with sqlite3.connect(path) as db:
            header = db.execute("SELECT * FROM repository_graphs").fetchall()
        with pytest.raises(ValueError, match="arrays"):
            store.save(identifier, invalid)
        assert normalized_rows(path, identifier) == before
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT * FROM repository_graphs").fetchall() == header
        with pytest.raises(ValueError, match="arrays"):
            store.save_new("Invalid", ".", invalid)
        assert store.resolve("Invalid") is None
