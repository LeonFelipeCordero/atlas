"""Transport-independent repository and graph values; no ORM types escape storage."""

from typing import Any, Protocol

from pydantic import BaseModel


class RepositoryError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class RepositoryDTO(BaseModel):
    id: str
    name: str
    location: str
    createdAt: int
    importedAt: int | None


class GraphStatsDTO(BaseModel):
    files: int
    symbols: int
    modules: int
    types: int
    callables: int
    nodes: int
    edges: int
    externalNodes: int
    parseErrors: int


class GraphDTO(BaseModel):
    repositoryId: str
    graphRevision: str
    schemaVersion: int | None
    indexedAt: str | None
    rootName: str | None
    rootPath: str | None
    importedAt: int
    stats: GraphStatsDTO


class ReportNodeDTO(BaseModel):
    stableKey: str
    parentStableKey: str | None = None
    type: str
    level: str
    kind: str
    name: str
    qualifiedName: str | None = None
    path: str | None = None
    startLine: int | None = None
    lineCount: int | None = None
    parameterCount: int | None = None
    cyclomaticComplexity: int | None = None
    loopNestedComplexity: int | None = None
    maxDecisionDepth: int | None = None


class ReportImportDTO(BaseModel):
    sourceStableKey: str
    targetStableKey: str
    type: str
    confidence: str
    path: str | None
    line: int | None
    evidence: str | None
    typeOnly: bool


class ReportFactsDTO(BaseModel):
    graphRevision: str
    nodes: list[ReportNodeDTO]
    imports: list[ReportImportDTO]


class RepositoryProtocol(Protocol):
    def register(self, name: str, location: str) -> RepositoryDTO: ...

    def list(self) -> list[RepositoryDTO]: ...

    def exists(self, identifier: str) -> bool: ...

    def resolve(self, name: str) -> str | None: ...

    def graph(self, identifier: str) -> GraphDTO | None: ...

    def report_facts(self, identifier: str) -> ReportFactsDTO | None: ...

    def save(self, identifier: str, artifact: dict[str, Any]) -> GraphDTO: ...

    def save_new(self, name: str, location: str, artifact: dict[str, Any]) -> GraphDTO: ...
