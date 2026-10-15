"""Candidate payloads share the graph's replacement transaction and file ownership."""

from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from atlas.persistence.database import migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore

from .graph_storage_fixture import graph_artifact, normalized_rows


def candidate_artifact() -> dict:
    artifact = graph_artifact()
    span = {"startByte": 3, "endByte": 4, "startLine": 1, "startColumn": 4, "endLine": 1, "endColumn": 5}
    candidate = {
        "id": "candidate-1", "path": "src/app.py", "language": "python",
        "sourceHash": "a" * 64, "kind": "arithmetic", "operator": "+",
        "span": span, "expressionSpan": {**span, "startByte": 0, "endByte": 6, "startColumn": 1, "endColumn": 7},
        "originalText": "+", "expressionText": "é + x",
        "callable": {"name": "run", "span": span, "originalText": "é + x\r\n"},
    }
    artifact["mutationCandidates"] = [candidate, {**candidate, "id": "candidate-2"}]
    del artifact["mutationCandidates"][1]["operator"]
    del artifact["mutationCandidates"][1]["callable"]
    artifact["mutationCandidateDiagnostics"] = [{
        "path": "src/app.py", "language": "python", "code": "unsupported",
        "message": "Exact diagnostic: é\n", "line": 1,
    }]
    return artifact


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "candidates.sqlite"
    migrate_database(path)
    return path


def candidate_rows(path: Path, identifier: str) -> list[tuple]:
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT * FROM graph_mutation_candidates WHERE repository_id=? ORDER BY ordinal", (identifier,),
        ).fetchall()


def test_exact_roundtrip_and_warning_separation(database: Path) -> None:
    artifact = candidate_artifact()
    with repository_session(database) as session:
        result = RepositoryStore(session).save_new("Candidates", ".", artifact)
    with repository_session(database) as session:
        store = RepositoryStore(session)
        facts = store.report_facts(result.repositoryId)
        assert facts is not None
        assert facts.mutationCandidates == artifact["mutationCandidates"]
        assert facts.mutationCandidateDiagnostics == artifact["mutationCandidateDiagnostics"]
        assert facts.diagnostics == artifact["diagnostics"]
        summary = store.graph(result.repositoryId)
        assert summary is not None and summary.stats.parseErrors == 1
    rows = candidate_rows(database, result.repositoryId)
    assert rows[0][1:9] == ("candidate-1", "file", 0, "src/app.py", "python", "a" * 64, "arithmetic", "+")
    assert rows[1][8] is None
    with sqlite3.connect(database) as db:
        diagnostic = db.execute("SELECT severity,message FROM graph_diagnostics WHERE ordinal=1").fetchone()
        assert diagnostic[0] == "warning"
        assert diagnostic[1].startswith("Mutation candidates: ")


def test_refresh_replaces_candidates_and_diagnostics(database: Path) -> None:
    artifact = candidate_artifact()
    with repository_session(database) as session:
        store = RepositoryStore(session)
        identifier = store.save_new("Refresh", ".", artifact).repositoryId
        artifact["mutationCandidates"] = [artifact["mutationCandidates"][1]]
        artifact["mutationCandidateDiagnostics"] = []
        store.save(identifier, artifact)
        facts = store.report_facts(identifier)
        assert facts is not None and facts.mutationCandidates == artifact["mutationCandidates"]
        assert facts.mutationCandidateDiagnostics == []
        store.save(identifier, graph_artifact())
        facts = store.report_facts(identifier)
        assert facts is not None and facts.mutationCandidates == []
        assert facts.mutationCandidateDiagnostics == []
    assert candidate_rows(database, identifier) == []


@pytest.mark.parametrize("table,key", [("graph_files", "node_key"), ("repository_graphs", "repository_id"), ("repositories", "id")])
def test_file_and_repository_cascades_are_scoped(database: Path, table: str, key: str) -> None:
    with repository_session(database) as session:
        store = RepositoryStore(session)
        first = store.save_new("First", ".", candidate_artifact()).repositoryId
        second = store.save_new("Second", ".", candidate_artifact()).repositoryId
    expected = candidate_rows(database, second)
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if table == "graph_files":
            db.execute("DELETE FROM graph_files WHERE repository_id=? AND node_key='file'", (first,))
        else:
            db.execute(f"DELETE FROM {table} WHERE {key}=?", (first,))
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert candidate_rows(database, first) == []
    assert candidate_rows(database, second) == expected


@pytest.mark.parametrize("new_registration", [False, True])
def test_late_failure_rolls_back_candidate_rows_and_graph(database: Path, new_registration: bool) -> None:
    artifact = candidate_artifact()
    with repository_session(database) as session:
        store = RepositoryStore(session)
        identifier = store.save_new("Atomic", ".", artifact).repositoryId
        before = store.report_facts(identifier)
        rows = normalized_rows(database, identifier), candidate_rows(database, identifier)
        with sqlite3.connect(database) as db:
            db.execute("CREATE TRIGGER fail_diagnostics BEFORE INSERT ON graph_diagnostics BEGIN SELECT RAISE(ABORT, 'late diagnostic failure'); END")
        changed = deepcopy(artifact)
        changed["mutationCandidates"][0]["originalText"] = "changed"
        with pytest.raises(Exception, match="late diagnostic failure"):
            if new_registration:
                store.save_new("Ghost", ".", changed)
            else:
                store.save(identifier, changed)
        assert store.resolve("Ghost") is None
        assert store.report_facts(identifier) == before
        assert (normalized_rows(database, identifier), candidate_rows(database, identifier)) == rows


def test_composite_file_fk_cannot_cross_repository(database: Path) -> None:
    with repository_session(database) as session:
        store = RepositoryStore(session)
        first = store.save_new("First", ".", candidate_artifact()).repositoryId
        second = store.save_new("Empty", ".", {"nodes": []}).repositoryId
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            db.execute(
                "INSERT INTO graph_mutation_candidates SELECT ?,candidate_id,file_key,ordinal,path,language,source_hash,kind,operator,payload FROM graph_mutation_candidates WHERE repository_id=?",
                (second, first),
            )
    assert candidate_rows(database, second) == []
