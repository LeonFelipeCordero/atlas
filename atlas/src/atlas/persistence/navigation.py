"""Bounded, repository-scoped SQL reads in an explicit read-only snapshot."""

import sqlite3
from contextlib import closing, contextmanager
from itertools import chain, product
from pathlib import Path
from typing import Generator

from atlas.domain.navigation import GraphSnapshot, NavigationError, Record
from atlas.persistence.database import default_database_path

REQUIRED_TABLES = {"repositories", "repository_graphs", "graph_nodes", "graph_files", "graph_symbols", "graph_node_metrics", "graph_node_decorators", "graph_edges", "graph_diagnostics"}
REQUIRED_INDEXES = {"graph_nodes_parent", "graph_nodes_name", "graph_nodes_path", "graph_edges_source", "graph_edges_target", "graph_diagnostics_path"}
NODE_COLUMNS = """n.node_key AS stableKey, n.parent_key AS parentStableKey,
 n.type, n.kind, n.level, n.name, n.language, n.qualified_name AS qualifiedName, n.path,
 s.start_line AS startLine, s.start_column AS startColumn, s.end_line AS endLine,
 s.end_column AS endColumn, s.signature, s.visibility"""
NODE_JOIN = "FROM graph_nodes n LEFT JOIN graph_symbols s ON s.repository_id=n.repository_id AND s.node_key=n.node_key"


@contextmanager
def navigation_reader(project: str, revision: str | None, path: str | Path | None = None) -> Generator["GraphReader", None, None]:
    target = (Path(path).expanduser() if path is not None else default_database_path()).resolve()
    try:
        with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            check_schema(connection)
            yield GraphReader(connection, project, revision)
            connection.rollback()
    except sqlite3.Error as error:
        raise NavigationError(f"Cannot read graph database {target}: {error}. Index the project after explicitly migrating the database.") from error


def check_schema(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table','index')").fetchall()
    tables = {row["name"] for row in rows if row["type"] == "table"}
    indexes = {row["name"] for row in rows if row["type"] == "index"}
    missing = sorted((REQUIRED_TABLES - tables) | (REQUIRED_INDEXES - indexes))
    if missing:
        raise NavigationError(f"Missing graph schema/index: {', '.join(missing)}. Explicitly migrate and index the project.")


class GraphReader:
    def __init__(self, connection: sqlite3.Connection, project: str, revision: str | None) -> None:
        self.connection = connection
        rows = connection.execute("SELECT id, location FROM repositories WHERE id=? OR lower(name)=lower(?) ORDER BY id LIMIT 2", (project, project)).fetchall()
        if len(rows) != 1:
            raise NavigationError("Project not found or ambiguous; use an explicit registered project ID")
        repository_id = rows[0]["id"]
        graph = connection.execute("SELECT graph_revision, indexed_at FROM repository_graphs WHERE repository_id=?", (repository_id,)).fetchone()
        if not graph or not graph["graph_revision"]:
            raise NavigationError("Project has no normalized graph; index it first")
        self.snapshot = GraphSnapshot(repository_id, graph["graph_revision"], graph["indexed_at"], rows[0]["location"])
        if revision is not None and revision != self.snapshot.revision:
            raise NavigationError(f"Stale graph revision: expected {revision}, current {self.snapshot.revision}")

    def _rows(self, sql: str, parameters: tuple[object, ...] = ()) -> list[Record]:
        return [dict(row) for row in self.connection.execute(sql, (self.snapshot.repository_id, *parameters)).fetchall()]

    def overview(self) -> Record:
        counts = self._rows("SELECT level, count(*) AS count FROM graph_nodes WHERE repository_id=? GROUP BY level ORDER BY level")
        relations = self._rows("SELECT relationship AS type, count(*) AS count FROM graph_edges WHERE repository_id=? GROUP BY relationship ORDER BY relationship")
        roots = self._rows(f"SELECT {NODE_COLUMNS} {NODE_JOIN} WHERE n.repository_id=? AND n.parent_key IS NULL ORDER BY n.node_key LIMIT 31")
        return {"levels": counts, "relations": relations, "roots": roots[:30], "truncated": len(roots) > 30}

    def find(self, query: str, limit: int) -> list[Record]:
        # instr treats user input literally, unlike SQL LIKE wildcards.
        sql = f"""SELECT {NODE_COLUMNS} {NODE_JOIN} WHERE n.repository_id=? AND
          (instr(lower(n.path),lower(?))>0 OR instr(lower(n.name),lower(?))>0 OR instr(lower(n.qualified_name),lower(?))>0 OR n.node_key=?)
          ORDER BY CASE WHEN n.node_key=? THEN 0 WHEN lower(n.path)=lower(?) THEN CASE WHEN n.level='file' THEN 1 ELSE 2 END
          WHEN lower(n.name)=lower(?) THEN 3 WHEN lower(n.qualified_name)=lower(?) THEN 4 ELSE 5 END,
          n.level='external', coalesce(n.path,''), n.name, n.node_key LIMIT ?"""
        return self._rows(sql, (query,) * 8 + (limit,))

    def node(self, key: str) -> Record:
        rows = self._rows(f"SELECT {NODE_COLUMNS} {NODE_JOIN} WHERE n.repository_id=? AND n.node_key=? LIMIT 1", (key,))
        if not rows:
            raise NavigationError(f"Node not found: {key}. Use find to obtain a stableKey.")
        node = rows[0]
        node["external"] = node["level"] == "external"
        metrics = self._rows("SELECT line_count AS lineCount, parameter_count AS parameterCount, base_complexity AS baseCyclomaticComplexity, nested_complexity AS nestedCyclomaticComplexity, loop_complexity AS loopNestedComplexity, total_complexity AS cyclomaticComplexity, max_decision_depth AS maxDecisionDepth FROM graph_node_metrics WHERE repository_id=? AND node_key=?", (key,))
        node["metrics"] = metrics[0] if metrics else None
        files = self._rows("SELECT byte_count AS bytes, sha256 FROM graph_files WHERE repository_id=? AND node_key=?", (key,))
        node["file"] = files[0] if files else None
        node["decorators"] = [row["decorator"] for row in self._rows("SELECT decorator FROM graph_node_decorators WHERE repository_id=? AND node_key=? ORDER BY ordinal LIMIT 101", (key,))]
        node["decoratorsTruncated"] = len(node["decorators"]) > 100
        node["decorators"] = node["decorators"][:100]
        return node

    def children(self, key: str, limit: int, offset: int) -> list[Record]:
        return self._rows(f"SELECT {NODE_COLUMNS} {NODE_JOIN} WHERE n.repository_id=? AND n.parent_key=? ORDER BY n.ordinal, n.node_key LIMIT ? OFFSET ?", (key, limit, offset))

    def edges(self, key: str, direction: str, relations: list[str], limit: int) -> list[Record]:
        columns = ["source_key", "target_key"] if direction == "both" else ["source_key" if direction == "out" else "target_key"]
        batches = (self._edge_rows(key, column, relation, limit) for column, relation in product(columns, relations))
        selected = {row["ordinal"]: row for row in chain.from_iterable(batches)}
        return [selected[ordinal] for ordinal in sorted(selected)[:limit]]

    def _edge_rows(self, key: str, column: str, relation: str, limit: int) -> list[Record]:
        # Equality on the index's first three columns streams ordinal order without
        # sorting a whole high-degree neighborhood (IN/OR can scan the repository).
        index = "graph_edges_source" if column == "source_key" else "graph_edges_target"
        sql = f"""SELECT ordinal, source_key AS sourceStableKey, target_key AS targetStableKey,
          relationship AS type, confidence, path, evidence, line, type_only AS typeOnly
          FROM graph_edges INDEXED BY {index} WHERE repository_id=? AND {column}=?
          AND relationship=? ORDER BY ordinal LIMIT ?"""
        rows = self._rows(sql, (key, relation, limit))
        for row in rows:
            row["typeOnly"] = bool(row["typeOnly"])
        return rows

    def diagnostics(self, paths: list[str], limit: int) -> list[Record]:
        placeholders = ",".join("?" for _ in paths)
        return self._rows(f"SELECT severity, path, language, message FROM graph_diagnostics WHERE repository_id=? AND path IN ({placeholders}) ORDER BY ordinal LIMIT ?", (*paths, limit))

    def file(self, path: str) -> list[Record]:
        return self._rows("SELECT n.node_key AS stableKey, f.sha256 FROM graph_nodes n JOIN graph_files f ON f.repository_id=n.repository_id AND f.node_key=n.node_key WHERE n.repository_id=? AND n.path=? ORDER BY n.node_key LIMIT 2", (path,))
