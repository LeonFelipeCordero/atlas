"""Focused graph CLI, traversal, isolation, snapshot and source safety checks."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner

from atlas.bootstrap import navigation_service
from atlas.cli.commands import main
from atlas.domain.navigation import NavigationError
from atlas.persistence.database import migrate_database, repository_session
from atlas.persistence.navigation import GraphReader, navigation_reader
from atlas.persistence.navigation_queries import adjacency
from atlas.persistence.repositories import RepositoryStore
from atlas.services.navigation import NavigationService
from tests.graph_storage_fixture import graph_artifact


@pytest.fixture
def graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    path = tmp_path / "atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    migrate_database(path)
    source = tmp_path / "src/app.py"
    source.parent.mkdir()
    source.write_text("def run():\n    worker()\n    return 1\n\ndef worker():\n    pass\n")
    artifact = graph_artifact()
    artifact["nodes"][2]["properties"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    artifact["edges"].append({**artifact["edges"][0], "sourceStableKey": "worker", "targetStableKey": "run"})
    artifact["diagnostics"].append({"severity": "warning", "path": "src/app.py", "language": "python", "message": "local warning"})
    with repository_session(path) as session:
        saved = RepositoryStore(session).save_new("Local", str(tmp_path), artifact)
    return path, saved.repositoryId, saved.graphRevision


def command(*args: str) -> dict:
    result = CliRunner().invoke(main, ["graph", "--project", "Local", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_cli_metadata_and_required_project(graph) -> None:
    overview = command("overview")
    assert overview["repositoryId"] == graph[1]
    assert overview["graphRevision"] == graph[2]
    assert overview["indexedAt"]
    assert overview["levels"]
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 2 and "--project" in result.output


def test_search_rank_ambiguity_and_literal_query(graph) -> None:
    path, identifier, _ = graph
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE graph_nodes SET name='run' WHERE repository_id=? AND node_key='worker'", (identifier,))
    results = command("find", "run")["nodes"]
    assert [node["stableKey"] for node in results] == ["run", "worker"]
    assert command("find", "run", "--limit", "1")["truncated"]
    assert command("find", "%")["nodes"] == []
    assert command("find", "src/app.py")["nodes"][0]["path"] == "src/app.py"
    error = CliRunner().invoke(main, ["graph", "--project", "Local", "show", "RUN"])
    assert error.exit_code == 1 and "Node not found" in error.output
    assert "Node not found" in json.loads(error.stderr)["error"]


def test_search_prefers_internal_declarations_and_exact_files(graph) -> None:
    with sqlite3.connect(graph[0]) as connection:
        connection.execute("UPDATE graph_nodes SET name='run' WHERE repository_id=? AND node_key='external'", (graph[1],))
    assert command("find", "run", "--limit", "1")["nodes"][0]["stableKey"] == "run"
    assert command("find", "src/app.py", "--limit", "1")["nodes"][0]["stableKey"] == "file"


def test_hierarchy_pagination_and_diagnostic_scope(graph) -> None:
    shown = command("show", "run")
    assert [node["stableKey"] for node in shown["ancestors"]] == ["file", "repository"]
    assert shown["node"]["signature"] == "def run():"
    assert shown["node"]["decorators"] == ["@trace", "@trace"]
    assert [row["message"] for row in shown["diagnostics"]] == ["local warning"]
    first = command("children", "file", "--limit", "1")
    assert first["nodes"][0]["stableKey"] == "run" and first["nextOffset"] == 1
    second = command("children", "file", "--limit", "1", "--offset", "1")
    assert second["nodes"][0]["stableKey"] == "worker" and not second["truncated"]


@pytest.mark.parametrize("direction", ["out", "in", "both"])
def test_directions_cycles_and_evidence(graph, direction) -> None:
    payload = command("context", "run", "--direction", direction, "--depth", "4")
    assert {node["stableKey"] for node in payload["nodes"]} == {"run", "worker"}
    assert not payload["truncated"]
    assert all(edge["confidence"] == "INFERRED" and edge["evidence"] == "worker()" for edge in payload["edges"])
    if direction == "out":
        assert payload["edges"][0]["sourceStableKey"] == "run"
    if direction == "in":
        assert payload["edges"][0]["sourceStableKey"] == "worker"


@pytest.mark.parametrize("option,value,reason", [("--depth", "0", "depth"), ("--max-nodes", "1", "maxNodes"), ("--max-edges", "1", "maxEdges")])
def test_context_cutoffs(graph, option, value, reason) -> None:
    payload = command("context", "run", option, value)
    assert payload["truncated"]
    assert reason in {boundary["reason"] for boundary in payload["boundaries"]}
    assert len(payload["nodes"]) <= payload["filters"]["maxNodes"]
    assert len(payload["edges"]) <= payload["filters"]["maxEdges"]


def test_external_and_type_only(graph) -> None:
    payload = command("context", "run", "--relations", "IMPORTS")
    assert payload["edges"][0]["typeOnly"] is True
    assert payload["boundaries"] == [{"stableKey": "external", "reason": "external_unresolved_or_ambiguous", "expandable": False}]


def driver(reader: GraphReader) -> sqlite3.Connection:
    """Test-only instrumentation of repository internals, never a production API."""
    return cast(sqlite3.Connection, reader._session.connection().connection.driver_connection)


def test_frontier_edge_queries_are_scoped_and_bounded(graph) -> None:
    with navigation_reader("Local", None) as reader:
        statements: list[str] = []
        driver(reader).set_trace_callback(statements.append)
        NavigationService(reader).context("run", "both", ["CALLS"], 4, 3, 2)
    edges = [sql for sql in statements if "FROM graph_edges" in sql]
    assert edges
    assert all(f"graph_edges.repository_id = '{graph[1]}'" in sql for sql in edges)
    assert all("LIMIT" in sql for sql in edges)
    assert all("INDEXED BY graph_edges_" in sql for sql in edges)
    assert all("graph_edges.relationship = 'CALLS'" in sql for sql in edges)


@pytest.mark.parametrize("column,index", [("source_key", "graph_edges_source"), ("target_key", "graph_edges_target")])
def test_adjacency_plan_streams_endpoint_relation_index(graph, column, index) -> None:
    with navigation_reader("Local", None) as reader:
        statement = adjacency(graph[1], "run", column == "source_key", "CALLS", 2)
        sql = str(statement.compile(dialect=reader._session.get_bind().dialect, compile_kwargs={"literal_binds": True}))
        assert f"INDEXED BY {index}" in sql
        plan = driver(reader).execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
    assert all("TEMP B-TREE" not in row[3] for row in plan)
    assert any("relationship=?" in row[3] for row in plan)


@pytest.mark.parametrize("direction", ["out", "in", "both"])
def test_adjacency_work_ignores_unrelated_edges(graph, direction) -> None:
    with sqlite3.connect(graph[0]) as connection:
        connection.executemany("INSERT INTO graph_edges (repository_id,ordinal,source_key,target_key,relationship,confidence,type_only) VALUES (?,?,'worker','worker','CALLS','INFERRED',0)", [(graph[1], ordinal) for ordinal in range(100, 10100)])
    with navigation_reader("Local", None) as reader:
        steps: list[None] = []

        def count_steps() -> int:
            steps.append(None)
            return 0

        driver(reader).set_progress_handler(count_steps, 100)
        assert reader.edges("repository", direction, ["CALLS", "REFERENCES"], 1) == []
    assert len(steps) < 10


def test_unknown_relation_is_a_usage_error(graph) -> None:
    result = CliRunner().invoke(main, ["graph", "--project", "Local", "context", "run", "--relations", "CALSS"])
    assert result.exit_code == 2 and "Choose comma-separated relations" in result.output


def test_path_found_unknown_and_not_found(graph) -> None:
    assert command("path", "run", "worker")["path"] == ["run", "worker"]
    assert command("path", "run", "worker", "--max-depth", "0")["status"] == "unknown"
    assert command("path", "run", "external", "--max-nodes", "1")["status"] == "unknown"
    assert command("path", "run", "external")["status"] == "not_found"
    assert command("path", "run", "run")["path"] == ["run"]


def test_repository_isolation(graph) -> None:
    path, identifier, _ = graph
    artifact = graph_artifact()
    artifact["nodes"][0]["name"] = "other-only"
    artifact["diagnostics"][0]["path"] = "src/app.py"
    with repository_session(path) as session:
        other = RepositoryStore(session).save_new("Other", ".", artifact)
    assert command("find", "other-only")["nodes"] == []
    assert [row["message"] for row in command("show", "run")["diagnostics"]] == ["local warning"]
    with navigation_service(other.repositoryId) as service:
        assert service.show("run")["node"]["name"] == "other-only"
        assert service.context("run", "out", ["CALLS"], 2, 30, 100)["repositoryId"] != identifier


def test_read_snapshot_and_revision(graph) -> None:
    path, identifier, revision = graph
    with navigation_reader(identifier, revision) as reader:
        with sqlite3.connect(path) as writer:
            writer.execute("UPDATE graph_nodes SET name='new' WHERE repository_id=? AND node_key='run'", (identifier,))
            writer.execute("UPDATE repository_graphs SET graph_revision='new' WHERE repository_id=?", (identifier,))
        assert reader.node("run")["name"] == "run"
        assert reader.snapshot.revision == revision
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            driver(reader).execute("DELETE FROM graph_nodes")
    result = CliRunner().invoke(main, ["graph", "--project", "Local", "--revision", revision, "overview"])
    assert result.exit_code == 1 and "Stale graph revision" in result.output
    with navigation_service(identifier) as service:
        assert service.show("run")["graphRevision"] == "new"


def test_missing_database_is_not_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "absent" / "database.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    result = CliRunner().invoke(main, ["graph", "--project", "Local", "overview"])
    assert result.exit_code == 1 and "Cannot read graph database" in result.output
    assert not path.parent.exists()


def test_missing_schema_and_index(tmp_path: Path, graph) -> None:
    empty = tmp_path / "empty.sqlite"
    with sqlite3.connect(empty):
        pass
    with pytest.raises(NavigationError, match="Missing graph schema/index"):
        with navigation_service("Local", path=empty):
            pass
    with sqlite3.connect(graph[0]) as connection:
        connection.execute("DROP INDEX graph_edges_source")
    with pytest.raises(NavigationError, match="graph_edges_source"):
        with navigation_service("Local"):
            pass


@pytest.mark.parametrize("separator", ["\u2028", "\u0085", "\f"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_source_spans_use_parser_lf_coordinates(graph, separator, newline) -> None:
    from atlas.services.repositories import analyze_folder

    root = graph[0].parent
    lines = [f'label = "first{separator}second"', "def run():", "    return 42"]
    (root / "src/app.py").write_bytes((newline.join(lines) + newline).encode("utf-8"))
    with repository_session(graph[0]) as session:
        RepositoryStore(session).save(graph[1], analyze_folder(root))
    key = command("find", "run")["nodes"][0]["stableKey"]
    source = command("source", key)["source"]
    assert source["status"] == "ok"
    assert (source["startLine"], source["endLine"]) == (2, 3)
    assert source["lines"] == lines[1:]
    file_source = command("source", "file:src/app.py")["source"]
    assert file_source["lines"] == lines


def test_source_verified_paged_changed_missing(graph) -> None:
    payload = command("source", "run", "--max-lines", "1")["source"]
    assert payload["status"] == "ok" and payload["lines"] == ["def run():"]
    assert payload["nextStartLine"] == 2
    page = command("source", "run", "--start-line", "2")["source"]
    assert page["lines"] == ["    worker()", "    return 1"]
    assert command("source", "worker")["source"]["status"] == "span_unavailable"
    source = graph[0].parent / "src/app.py"
    source.write_text("changed\n")
    changed = command("source", "run")["source"]
    assert changed["status"] == "changed" and "lines" not in changed
    source.unlink()
    assert command("source", "run")["source"]["status"] == "missing"


@pytest.mark.parametrize("unsafe", ["../outside.py", "/outside.py", "src/escape.py"])
def test_source_unsafe_paths_and_symlink(graph, tmp_path: Path, unsafe: str) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("secret\n")
    (tmp_path / "src/escape.py").symlink_to(outside)
    with sqlite3.connect(graph[0]) as connection:
        connection.execute("UPDATE graph_nodes SET path=? WHERE repository_id=? AND node_key IN ('run','file')", (unsafe, graph[1]))
    assert command("source", "run")["source"] == {"status": "unsafe", "path": unsafe}
    outside.unlink()


def test_source_fifo_never_blocks(graph) -> None:
    source = graph[0].parent / "src/app.py"
    source.unlink()
    os.mkfifo(source)
    result = subprocess.run([sys.executable, "-m", "atlas", "graph", "--project", "Local", "source", "run"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["source"]["status"] == "unreadable"


def test_source_symlink_loop_is_structured(graph) -> None:
    source = graph[0].parent / "src/app.py"
    source.unlink()
    source.symlink_to(source)
    assert command("source", "run")["source"]["status"] in {"unsafe", "unreadable"}


def test_source_file_size_is_bounded(graph) -> None:
    from atlas.services.navigation_source import MAX_FILE_BYTES

    source = graph[0].parent / "src/app.py"
    with source.open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)
    payload = command("source", "run")["source"]
    assert payload["status"] == "too_large" and "lines" not in payload


def test_source_long_line_output_is_bounded(graph) -> None:
    source = graph[0].parent / "src/app.py"
    source.write_text("x" * 2_000_000)
    with sqlite3.connect(graph[0]) as connection:
        connection.execute("UPDATE graph_files SET sha256=? WHERE repository_id=?", (hashlib.sha256(source.read_bytes()).hexdigest(), graph[1]))
    payload = command("source", "run", "--max-lines", "1")["source"]
    assert payload["status"] == "too_large" and "lines" not in payload
