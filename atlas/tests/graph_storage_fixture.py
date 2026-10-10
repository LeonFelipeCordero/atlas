"""Small ordered/unordered graph fixtures and isolated storage helpers."""

import sqlite3
from pathlib import Path
from typing import Any

from alembic.config import Config

HEAD = "0004_drop_graph_artifact"
GRAPH_TABLES = (
    "graph_nodes", "graph_files", "graph_symbols", "graph_node_metrics",
    "graph_node_decorators", "graph_edges", "graph_diagnostics",
)


def _node(key: str, level: str, parent: str | None, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "stableKey": key, "parentStableKey": parent, "type": level, "kind": level,
        "level": level, "language": "python", "name": key, "qualifiedName": key,
        "path": "src/app.py", "properties": properties,
    }


def graph_artifact() -> dict[str, Any]:
    run = _node("run", "callable", "file", {
        "visibility": None, "decorators": ["@trace", "@trace"],
        "lineCount": 0, "parameterCount": 0, "baseCyclomaticComplexity": 1,
        "nestedCyclomaticComplexity": 0, "loopNestedComplexity": 0,
        "cyclomaticComplexity": 1, "maxDecisionDepth": 0, "futureMetric": [None, 2],
    })
    run.update(type="function", kind="function", startLine=1, startColumn=1, endLine=3, endColumn=2, signature="def run():")
    worker = _node("worker", "callable", "file", {"visibility": None, "decorators": []})
    worker.update(type="function", kind="function", signature=None)
    file = _node("file", "file", "repository", {"bytes": 40, "sha256": "a" * 64})
    root = _node("repository", "repository", None, {"absolutePath": "/unavailable"})
    external = _node("external", "external", "repository", {})
    external.update(path=None, name="")
    call = {
        "sourceStableKey": "run", "targetStableKey": "worker", "type": "CALLS",
        "confidence": "INFERRED", "path": "src/app.py", "line": 2, "evidence": "worker()",
    }
    return {
        "schemaVersion": 2,
        "repository": {"name": "Analyzed root", "path": "/unavailable", "indexedAt": "2026-10-04T05:38:39+00:00"},
        # Children precede parents to exercise deferred parent foreign keys.
        "nodes": [run, worker, file, external, root],
        "edges": [call, dict(call), {**call, "targetStableKey": "external", "type": "IMPORTS", "typeOnly": True}],
        "diagnostics": [{"severity": "error", "path": "missing.py", "language": "python", "message": "parse failed"}],
        "stats": {"unmodeled": 99}, "views": {"future": []},
        "circularDependencies": None, "future": {"values": [1, None, "École"]},
    }


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def normalized_rows(path: Path, repository_id: str) -> dict[str, list[tuple[Any, ...]]]:
    with sqlite3.connect(path) as database:
        return {
            table: database.execute(f"SELECT * FROM {table} WHERE repository_id=? ORDER BY 1, 2, 3", (repository_id,)).fetchall()
            for table in GRAPH_TABLES
        }
