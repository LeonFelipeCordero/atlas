"""Normalized graph facts, transaction boundaries, and SQLite snapshot reads."""

from dataclasses import asdict
import re
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from atlas.persistence.database import create_engine, migrate_database, repository_session
from atlas.metrics.report import build_report, build_artifact_report
from atlas.persistence.models import (
    GraphEdgeRow, GraphFileRow, GraphNodeDecoratorRow, GraphNodeMetricRow,
    GraphNodeRow, GraphSymbolRow, RepositoryGraphRow,
)
from atlas.persistence.repositories import RepositoryStore as RuntimeRepositoryStore
from sqlalchemy import select
from sqlalchemy.orm import Session

from .graph_storage_fixture import GRAPH_TABLES, graph_artifact, normalized_rows
from tests.coffee_fixture import LANGUAGES, coffee_graph


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "graph.sqlite"
    migrate_database(path)
    return path


def header(path: Path, identifier: str) -> tuple:
    with sqlite3.connect(path) as db:
        return db.execute("SELECT * FROM repository_graphs WHERE repository_id=?", (identifier,)).fetchone()


def fail_edges(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_edges BEFORE INSERT ON graph_edges BEGIN SELECT RAISE(ABORT, 'late edge failure'); END")


def assert_saved(store: RuntimeRepositoryStore, identifier: str, artifact: dict) -> None:
    graph = store.graph(identifier)
    assert graph is not None and graph.schemaVersion == artifact.get("schemaVersion")
    assert graph.stats.nodes == len(artifact.get("nodes", []))
    assert graph.stats.edges == len(artifact.get("edges", []))
    facts = store.report_facts(identifier)
    assert facts is not None and facts.graphRevision == graph.graphRevision
    assert build_report(facts) == build_artifact_report(artifact)


def test_full_normalized_facts(database: Path) -> None:
    artifact = graph_artifact()
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        result = store.save_new("Registered", "elsewhere", artifact)
        identifier = result.repositoryId
        row = session.get(RepositoryGraphRow, identifier)
        assert row is not None
        assert_saved(store, identifier, artifact)
        assert "artifact" not in RepositoryGraphRow.__table__.columns
        assert row.repository_id == identifier
        assert row.graph_revision is not None
        assert re.fullmatch(r"[0-9a-f]{32}", row.graph_revision)
        assert (row.schema_version, row.indexed_at, row.root_name, row.root_path) == (
            2, artifact["repository"]["indexedAt"], "Analyzed root", "/unavailable",
        )
        assert row.imported_at == result.importedAt
        nodes = session.scalars(select(GraphNodeRow).order_by(GraphNodeRow.ordinal)).all()
        assert [(n.node_key, n.parent_key, n.ordinal) for n in nodes] == [
            ("run", "file", 0), ("worker", "file", 1), ("file", "repository", 2),
            ("external", "repository", 3), ("repository", None, 4),
        ]
        for node, raw in zip(nodes, artifact["nodes"], strict=True):
            assert (node.type, node.kind, node.level, node.name, node.language, node.qualified_name, node.path) == (
                raw["type"], raw["kind"], raw["level"], raw["name"], raw["language"], raw["qualifiedName"], raw["path"],
            )
        file = session.get(GraphFileRow, (identifier, "file"))
        assert file is not None
        assert (file.byte_count, file.sha256) == (40, "a" * 64)
        run = session.get(GraphSymbolRow, (identifier, "run"))
        assert run is not None
        assert (run.start_line, run.start_column, run.end_line, run.end_column, run.signature, run.visibility) == (1, 1, 3, 2, "def run():", None)
        worker = session.get(GraphSymbolRow, (identifier, "worker"))
        assert worker is not None
        assert (worker.start_line, worker.start_column, worker.end_line, worker.end_column, worker.signature, worker.visibility) == (None,) * 6
        metric = session.get(GraphNodeMetricRow, (identifier, "run"))
        assert metric is not None
        assert (metric.line_count, metric.parameter_count, metric.base_complexity, metric.nested_complexity, metric.loop_complexity, metric.total_complexity, metric.max_decision_depth) == (0, 0, 1, 0, 0, 1, 0)
        assert session.get(GraphNodeMetricRow, (identifier, "worker")) is None
        decorators = session.scalars(select(GraphNodeDecoratorRow).order_by(GraphNodeDecoratorRow.ordinal)).all()
        assert [(d.node_key, d.ordinal, d.decorator) for d in decorators] == [("run", 0, "@trace"), ("run", 1, "@trace")]
        edges = session.scalars(select(GraphEdgeRow).order_by(GraphEdgeRow.ordinal)).all()
        assert [(e.ordinal, e.source_key, e.target_key, e.relationship, e.confidence, e.path, e.evidence, e.line, e.type_only) for e in edges] == [
            (0, "run", "worker", "CALLS", "INFERRED", "src/app.py", "worker()", 2, False),
            (1, "run", "worker", "CALLS", "INFERRED", "src/app.py", "worker()", 2, False),
            (2, "run", "external", "IMPORTS", "INFERRED", "src/app.py", "worker()", 2, True),
        ]
    rows = normalized_rows(database, identifier)
    assert [len(rows[t]) for t in GRAPH_TABLES] == [5, 1, 2, 1, 2, 3, 1]
    assert rows["graph_diagnostics"] == [(identifier, 0, "error", "missing.py", "python", "parse failed")]
    assert rows["graph_node_metrics"] == [(identifier, "run", 0, 0, 1, 0, 0, 1, 0)]
    assert rows["graph_symbols"][1] == (identifier, "worker", None, None, None, None, None, None)


def test_explicit_null_measurement_is_present_not_zero(database: Path) -> None:
    artifact = graph_artifact()
    artifact["nodes"][1]["properties"]["lineCount"] = None
    with repository_session(database) as session:
        result = RuntimeRepositoryStore(session).save_new("Nulls", ".", artifact)
    rows = normalized_rows(database, result.repositoryId)
    assert rows["graph_node_metrics"][1] == (result.repositoryId, "worker", None, None, None, None, None, None, None)
    with repository_session(database) as session:
        facts = RuntimeRepositoryStore(session).report_facts(result.repositoryId)
        assert facts is not None
        assert facts.nodes[0].lineCount == 0
        assert facts.nodes[1].lineCount is None


@pytest.mark.parametrize("table", ["repository_graphs", "repositories"])
def test_scoped_cascade_and_same_keys(database: Path, table: str) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        first = store.save_new("First", ".", graph_artifact()).repositoryId
        second = store.save_new("Second", ".", graph_artifact()).repositoryId
    expected = normalized_rows(database, second)
    assert all(normalized_rows(database, first).values())
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        column = "id" if table == "repositories" else "repository_id"
        db.execute(f"DELETE FROM {table} WHERE {column}=?", (first,))
    assert all(not rows for rows in normalized_rows(database, first).values())
    assert normalized_rows(database, second) == expected
    assert header(database, first) is None


@pytest.mark.parametrize("reference", ["parent", "source", "target"])
def test_composite_references_cannot_cross_repositories(database: Path, reference: str) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        first = store.save_new("First", ".", graph_artifact()).repositoryId
        empty = {**graph_artifact(), "nodes": [], "edges": [], "diagnostics": []}
        second = store.save_new("Second", ".", empty).repositoryId
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if reference == "parent":
            db.execute("INSERT INTO graph_nodes (repository_id,node_key,parent_key,ordinal,type,kind,level,name) VALUES (?, 'child', 'run', 0, 'x', 'x', 'x', 'x')", (second,))
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                db.commit()
        else:
            db.execute("INSERT INTO graph_nodes (repository_id,node_key,ordinal,type,kind,level,name) VALUES (?, 'local', 0, 'x', 'x', 'x', 'x')", (second,))
            source, target = ("run", "local") if reference == "source" else ("local", "run")
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                db.execute("INSERT INTO graph_edges (repository_id,ordinal,source_key,target_key,relationship,confidence,type_only) VALUES (?,0,?,?,'CALLS','INFERRED',0)", (second, source, target))
        db.rollback()
    assert len(normalized_rows(database, first)["graph_nodes"]) == 5
    assert not normalized_rows(database, second)["graph_nodes"]


def replacement() -> dict:
    artifact = graph_artifact()
    artifact["nodes"] = [artifact["nodes"][-1]]
    artifact["nodes"][0]["properties"] = {}
    artifact["edges"] = []
    artifact["diagnostics"] = []
    return artifact


def test_replacement_removes_stale_facts_and_always_changes_revision(database: Path) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        identifier = store.save_new("Replace", ".", graph_artifact()).repositoryId
        previous = header(database, identifier)[2]
        for _ in range(2):
            artifact = replacement()
            store.save(identifier, artifact)
            current = header(database, identifier)
            assert current[2] != previous
            previous = current[2]
            assert_saved(store, identifier, artifact)
            rows = normalized_rows(database, identifier)
            assert len(rows.pop("graph_nodes")) == 1
            assert not any(rows.values())


def test_late_replacement_failure_restores_entire_snapshot_and_session(database: Path) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        identifier = store.save_new("Atomic", ".", graph_artifact()).repositoryId
        before = (header(database, identifier), normalized_rows(database, identifier))
        fail_edges(database)
        artifact = deepcopy(graph_artifact())
        artifact["nodes"][0]["properties"]["lineCount"] = 99
        artifact["repository"]["name"] = "Changed"
        with pytest.raises(Exception, match="late edge failure"):
            store.save(identifier, artifact)
        assert (header(database, identifier), normalized_rows(database, identifier)) == before
        assert_saved(store, identifier, graph_artifact())
        store.save(identifier, replacement())
        assert_saved(store, identifier, replacement())


@pytest.mark.parametrize("failure", ["invalid_collection", "late_edge"])
def test_save_new_failure_leaves_no_pending_or_ghost_registration(database: Path, failure: str) -> None:
    artifact = graph_artifact()
    if failure == "invalid_collection":
        artifact["nodes"] = {}
    else:
        fail_edges(database)
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        with pytest.raises(Exception, match="arrays|late edge failure"):
            store.save_new("Ghost", ".", artifact)
        assert not session.new
        assert store.list() == []
        assert store.resolve("Ghost") is None
        assert store.save_new("Reusable", ".", replacement()).stats.nodes == 1
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM repositories").fetchone() == (1,)
        assert db.execute("SELECT count(*) FROM repository_graphs").fetchone() == (1,)


@pytest.mark.parametrize("failure", ["cycle", "parent", "source", "target"])
def test_invalid_graph_rolls_back_existing_snapshot(database: Path, failure: str) -> None:
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        identifier = store.save_new("Invalid", ".", graph_artifact()).repositoryId
        before = (header(database, identifier), normalized_rows(database, identifier))
        artifact = graph_artifact()
        if failure == "cycle":
            artifact["nodes"][-1]["parentStableKey"] = "run"
        elif failure == "parent":
            artifact["nodes"][0]["parentStableKey"] = "missing"
        else:
            artifact["edges"][0][f"{failure}StableKey"] = "missing"
        with pytest.raises(Exception, match="cyclic|FOREIGN KEY"):
            store.save(identifier, artifact)
        assert (header(database, identifier), normalized_rows(database, identifier)) == before
        assert_saved(store, identifier, graph_artifact())


def connection_rows(connection, identifier: str) -> dict:
    return {table: connection.exec_driver_sql(f"SELECT * FROM {table} WHERE repository_id=? ORDER BY 1,2,3", (identifier,)).fetchall() for table in GRAPH_TABLES}


def test_wal_reader_keeps_header_and_rows_in_one_snapshot(database: Path) -> None:
    with repository_session(database) as session:
        identifier = RuntimeRepositoryStore(session).save_new("WAL", ".", graph_artifact()).repositoryId
    old_header = header(database, identifier)
    old_rows = normalized_rows(database, identifier)
    engine = create_engine(database)
    try:
        with engine.connect() as reader:
            transaction = reader.begin()
            assert reader.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert tuple(reader.exec_driver_sql("SELECT * FROM repository_graphs WHERE repository_id=?", (identifier,)).one()) == old_header
            with Session(engine) as writer:
                RuntimeRepositoryStore(writer).save(identifier, replacement())
            assert connection_rows(reader, identifier) == old_rows
            assert tuple(reader.exec_driver_sql("SELECT * FROM repository_graphs WHERE repository_id=?", (identifier,)).one()) == old_header
            transaction.commit()
            assert connection_rows(reader, identifier) == normalized_rows(database, identifier) != old_rows
            assert reader.exec_driver_sql("SELECT graph_revision FROM repository_graphs WHERE repository_id=?", (identifier,)).scalar() != old_header[2]
    finally:
        engine.dispose()


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_graphs_write_all_nodes_and_edge_occurrences(database: Path, language: str) -> None:
    artifact = asdict(coffee_graph(language))
    with repository_session(database) as session:
        store = RuntimeRepositoryStore(session)
        result = store.save_new(language, ".", artifact)
        assert_saved(store, result.repositoryId, artifact)
    rows = normalized_rows(database, result.repositoryId)
    assert len(rows["graph_nodes"]) == len(artifact["nodes"])
    assert len(rows["graph_edges"]) == len(artifact["edges"])
    assert {row[1] for row in rows["graph_nodes"]} == {node["stableKey"] for node in artifact["nodes"]}


@pytest.mark.parametrize("value", [None, False, True, 1, "true"])
def test_type_only_records_literal_true(database: Path, value) -> None:
    artifact = graph_artifact()
    artifact["edges"][0]["typeOnly"] = value
    with repository_session(database) as session:
        result = RuntimeRepositoryStore(session).save_new("Type only", ".", artifact)
    assert normalized_rows(database, result.repositoryId)["graph_edges"][0][-1] == int(value is True)
