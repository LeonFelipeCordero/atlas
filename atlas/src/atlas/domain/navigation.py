"""Read-only graph navigation contracts, independent of database and CLI."""

from dataclasses import dataclass
from typing import Any, Protocol

Record = dict[str, Any]


class NavigationError(Exception):
    """An actionable graph navigation failure."""


@dataclass(frozen=True)
class GraphSnapshot:
    repository_id: str
    revision: str
    indexed_at: str | None
    root: str

    def metadata(self) -> Record:
        return {"repositoryId": self.repository_id, "graphRevision": self.revision, "indexedAt": self.indexed_at}


@dataclass(frozen=True)
class EdgeRequest:
    key: str
    direction: str
    relations: list[str]
    limit: int


@dataclass(frozen=True)
class TraversalRequest:
    key: str
    direction: str
    relations: list[str]
    depth: int
    max_nodes: int
    max_edges: int


@dataclass(frozen=True)
class PathRequest:
    target: str
    traversal: TraversalRequest


@dataclass(frozen=True)
class SourceOptions:
    max_lines: int
    start_line: int | None


class NavigationReader(Protocol):
    snapshot: GraphSnapshot

    def overview(self) -> Record: ...
    def find(self, query: str, limit: int) -> list[Record]: ...
    def node(self, key: str) -> Record: ...
    def children(self, key: str, limit: int, offset: int) -> list[Record]: ...
    def edges(self, request: EdgeRequest) -> list[Record]: ...
    def diagnostics(self, paths: list[str], limit: int) -> list[Record]: ...
    def file(self, path: str) -> list[Record]: ...
