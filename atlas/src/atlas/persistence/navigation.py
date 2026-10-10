"""Bounded, repository-scoped mapped ORM reads in one read-only snapshot."""

from contextlib import contextmanager
from itertools import chain, product
from pathlib import Path
from typing import Generator

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from atlas.domain.navigation import EdgeRequest, GraphSnapshot, NavigationError, Record
from .models import (
    GraphDiagnosticRow, GraphEdgeRow, GraphFileRow, GraphNodeDecoratorRow,
    GraphNodeRow, RepositoryGraphRow, RepositoryRow,
)
from .navigation_database import readonly_session
from .navigation_queries import AdjacencyRequest, adjacency, metrics, nodes


@contextmanager
def navigation_reader(project: str, revision: str | None, path: str | Path | None = None) -> Generator["GraphReader", None, None]:
    """Construct a repository privately for the service-owned factory."""
    with readonly_session(path) as session:
        yield GraphReader(session, project, revision)


class GraphReader:
    def __init__(self, session: Session, project: str, revision: str | None) -> None:
        self._session = session
        rows = session.execute(select(RepositoryRow.id, RepositoryRow.location).where(
            or_(RepositoryRow.id == project, func.lower(RepositoryRow.name) == func.lower(project)),
        ).order_by(RepositoryRow.id).limit(2)).all()
        if len(rows) != 1:
            raise NavigationError("Project not found or ambiguous; use an explicit registered project ID")
        repository_id, location = rows[0]
        graph = session.get(RepositoryGraphRow, repository_id)
        if not graph or not graph.graph_revision:
            raise NavigationError("Project has no normalized graph; index it first")
        self.snapshot = GraphSnapshot(repository_id, graph.graph_revision, graph.indexed_at, location)
        if revision is not None and revision != self.snapshot.revision:
            raise NavigationError(f"Stale graph revision: expected {revision}, current {self.snapshot.revision}")

    def _rows(self, statement: Select) -> list[Record]:
        return [dict(row) for row in self._session.execute(statement).mappings()]

    def overview(self) -> Record:
        node, edge = GraphNodeRow, GraphEdgeRow
        identifier = self.snapshot.repository_id
        counts = self._rows(select(node.level, func.count().label("count")).where(
            node.repository_id == identifier,
        ).group_by(node.level).order_by(node.level))
        relations = self._rows(select(edge.relationship.label("type"), func.count().label("count")).where(
            edge.repository_id == identifier,
        ).group_by(edge.relationship).order_by(edge.relationship))
        roots = self._rows(nodes(identifier).where(node.parent_key.is_(None)).order_by(node.node_key).limit(31))
        return {"levels": counts, "relations": relations, "roots": roots[:30], "truncated": len(roots) > 30}

    def find(self, query: str, limit: int) -> list[Record]:
        node = GraphNodeRow
        # instr treats input literally rather than interpreting LIKE wildcards.
        match = or_(
            func.instr(func.lower(node.path), func.lower(query)) > 0,
            func.instr(func.lower(node.name), func.lower(query)) > 0,
            func.instr(func.lower(node.qualified_name), func.lower(query)) > 0,
            node.node_key == query,
        )
        rank = case(
            (node.node_key == query, 0),
            (func.lower(node.path) == func.lower(query), case((node.level == "file", 1), else_=2)),
            (func.lower(node.name) == func.lower(query), 3),
            (func.lower(node.qualified_name) == func.lower(query), 4), else_=5,
        )
        return self._rows(nodes(self.snapshot.repository_id).where(match).order_by(
            rank, node.level == "external", func.coalesce(node.path, ""), node.name, node.node_key,
        ).limit(limit))

    def node(self, key: str) -> Record:
        identifier = self.snapshot.repository_id
        rows = self._rows(nodes(identifier).where(GraphNodeRow.node_key == key).limit(1))
        if not rows:
            raise NavigationError(f"Node not found: {key}. Use find to obtain a stableKey.")
        node = rows[0]
        node["external"] = node["level"] == "external"
        values = self._rows(metrics(identifier, key))
        node["metrics"] = values[0] if values else None
        file = GraphFileRow
        files = self._rows(select(file.byte_count.label("bytes"), file.sha256).where(
            file.repository_id == identifier, file.node_key == key,
        ))
        node["file"] = files[0] if files else None
        decorator = GraphNodeDecoratorRow
        decorators = self._rows(select(decorator.decorator).where(
            decorator.repository_id == identifier, decorator.node_key == key,
        ).order_by(decorator.ordinal).limit(101))
        node["decoratorsTruncated"] = len(decorators) > 100
        node["decorators"] = [row["decorator"] for row in decorators[:100]]
        return node

    def children(self, key: str, limit: int, offset: int) -> list[Record]:
        node = GraphNodeRow
        return self._rows(nodes(self.snapshot.repository_id).where(node.parent_key == key).order_by(
            node.ordinal, node.node_key,
        ).limit(limit).offset(offset))

    def edges(self, request: EdgeRequest) -> list[Record]:
        directions = [True, False] if request.direction == "both" else [request.direction == "out"]
        batches = (self._rows(adjacency(AdjacencyRequest(
            self.snapshot.repository_id, request.key, outgoing, relation, request.limit,
        ))) for outgoing, relation in product(directions, request.relations))
        selected = {row["ordinal"]: row for row in chain.from_iterable(batches)}
        return [selected[ordinal] for ordinal in sorted(selected)[:request.limit]]

    def diagnostics(self, paths: list[str], limit: int) -> list[Record]:
        diagnostic = GraphDiagnosticRow
        return self._rows(select(diagnostic.severity, diagnostic.path, diagnostic.language, diagnostic.message).where(
            diagnostic.repository_id == self.snapshot.repository_id, diagnostic.path.in_(paths),
        ).order_by(diagnostic.ordinal).limit(limit))

    def file(self, path: str) -> list[Record]:
        node, file = GraphNodeRow, GraphFileRow
        return self._rows(select(node.node_key.label("stableKey"), file.sha256).join(
            file, (file.repository_id == node.repository_id) & (file.node_key == node.node_key),
        ).where(node.repository_id == self.snapshot.repository_id, node.path == path).order_by(node.node_key).limit(2))
