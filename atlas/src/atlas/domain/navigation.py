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
        """Return response metadata identifying this repository's indexed revision."""
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

    def overview(self) -> Record:
        """Return level/relation counts and bounded roots from the selected snapshot."""
        ...

    def find(self, query: str, limit: int) -> list[Record]:
        """Return ranked name/path/key matches, capped at limit."""
        ...

    def node(self, key: str) -> Record:
        """Return a stable key's node details, or raise NavigationError if absent."""
        ...

    def children(self, key: str, limit: int, offset: int) -> list[Record]:
        """Return a page of direct children in indexed artifact order."""
        ...

    def edges(self, request: EdgeRequest) -> list[Record]:
        """Return bounded adjacency filtered by direction and relation types."""
        ...

    def diagnostics(self, paths: list[str], limit: int) -> list[Record]:
        """Return bounded diagnostics for exact indexed paths in artifact order."""
        ...

    def file(self, path: str) -> list[Record]:
        """Return up to two file keys/hashes for an exact path to detect ambiguity."""
        ...
