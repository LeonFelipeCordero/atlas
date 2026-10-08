"""JSON-shaped schemas for repository graphs and projected dependency views.

TypedDicts describe field presence without changing dictionary serialization.
``MODEL_CONFIG`` enables strict Pydantic validation, rejects unknown fields, and
validates assignments when used by the artifact dataclass. Optional source
coordinates are one-based; counts and hierarchy depths are nonnegative.
"""

from dataclasses import field
from pathlib import Path
from typing import Any, Literal

from pydantic.dataclasses import dataclass

from pydantic import ConfigDict, NonNegativeInt, PositiveInt
from typing_extensions import NotRequired, TypedDict

MODEL_CONFIG = ConfigDict(strict=True, extra="forbid", validate_assignment=True)

Level = Literal[
    "repository", "module", "file", "type", "callable", "symbol", "external"
]
Relationship = Literal["CONTAINS", "CALLS", "REFERENCES", "IMPORTS", "INHERITS"]
Confidence = Literal["EXTRACTED", "INFERRED"]


class RepositoryMetadata(TypedDict, total=False):
    """Optional repository identity, indexing timestamp, and detected languages."""

    path: str
    name: str
    indexedAt: str
    languages: list[str]


class GraphNode(TypedDict):
    """Stable graph entity with parent, root-first ancestry, and source metadata."""

    stableKey: str
    type: str
    kind: str
    level: Level
    language: str | None
    name: str
    qualifiedName: str
    path: str | None
    parentStableKey: str | None
    startLine: NotRequired[PositiveInt]
    startColumn: NotRequired[PositiveInt]
    endLine: NotRequired[PositiveInt]
    endColumn: NotRequired[PositiveInt]
    signature: NotRequired[str | None]
    properties: dict[str, Any]
    depth: NonNegativeInt
    ancestorStableKeys: list[str]


class GraphEdge(TypedDict):
    """Directed relationship with provenance and enriched endpoint classifications."""

    sourceStableKey: str
    targetStableKey: str
    type: Relationship
    confidence: Confidence
    path: str
    line: PositiveInt
    evidence: str | None
    typeOnly: NotRequired[bool]
    sourceType: str
    sourceKind: str
    sourceLevel: Level
    targetType: str
    targetKind: str
    targetLevel: Level


class ProjectedEdge(TypedDict):
    """Aggregated dependency between same-level ancestors, with evidence counts."""

    sourceStableKey: str
    targetStableKey: str
    type: Literal["DEPENDS_ON"]
    level: Literal["module", "file", "type", "callable"]
    count: PositiveInt
    relationshipCounts: dict[Relationship, PositiveInt]
    confidenceCounts: dict[Confidence, PositiveInt]


class GraphView(TypedDict):
    """Node keys and aggregated dependencies for one hierarchy level."""

    nodes: list[str]
    edges: list[ProjectedEdge]


class Diagnostic(TypedDict):
    """Parse error associated with a repository-relative source path and language."""

    severity: Literal["error"]
    path: str
    language: str
    message: str


@dataclass(config=MODEL_CONFIG)
class SourceFile:
    """Validated source record: POSIX relative path, absolute path, language, bytes."""

    path: str
    absolute_path: Path
    language: str
    source: bytes


@dataclass(frozen=True, config=MODEL_CONFIG)
class Complexity:
    """Immutable base, deep-decision, nested-loop, total, and max-depth metrics."""

    baseCyclomaticComplexity: int
    nestedCyclomaticComplexity: int
    loopNestedComplexity: int
    cyclomaticComplexity: int
    maxDecisionDepth: int


@dataclass(config=MODEL_CONFIG)
class Symbol:
    """Declaration metadata, source span, parent key, and optional complexity."""

    key: str
    file_path: str
    language: str
    name: str
    qualified_name: str
    kind: str
    parent_key: str
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    signature: str | None
    visibility: str | None
    decorators: list[str]
    complexity: Complexity | None = None


@dataclass(config=MODEL_CONFIG)
class Import:
    """Unresolved import source and its one-based line in a file."""

    file_path: str
    source: str
    line: int


@dataclass(config=MODEL_CONFIG)
class Call:
    """Call-site span and evidence, with target hints for safe resolution."""

    file_path: str
    name: str
    start_byte: int
    end_byte: int
    line: int
    evidence: str
    bare_target: bool = False
    qualifier: str | None = None
    relationship: Literal["CALLS", "REFERENCES"] = "CALLS"


@dataclass(config=MODEL_CONFIG)
class Inheritance:
    """Unresolved base-type reference attached to a declaring symbol."""

    source_key: str
    file_path: str
    language: str
    target_name: str
    line: int
    evidence: str


@dataclass(config=MODEL_CONFIG)
class ParsedFile:
    """Source, SHA-256 digest, records, and any native processing error."""

    source: SourceFile
    content_hash: str
    parse_error: str | None
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    inheritances: list[Inheritance] = field(default_factory=list)


@dataclass(config=MODEL_CONFIG)
class ParsedRepository:
    """Ordered parsed files with flattened, non-deduplicated record views."""

    files: list[ParsedFile]

    @property
    def symbols(self) -> list[Symbol]:
        """Access declarations across files in repository order.

        Args:
            None; access as a property on a repository.
        Returns:
            A new list containing the original Symbol objects, in file order.
        Raises:
            None for valid repository records.
        Examples:
            >>> ParsedRepository([]).symbols
            []
        """
        return [symbol for file in self.files for symbol in file.symbols]

    @property
    def imports(self) -> list[Import]:
        """Access unresolved imports across files in repository order.

        Args:
            None; access as a property on a repository.
        Returns:
            A new list containing the original Import objects, in file order.
        Raises:
            None for valid repository records.
        Examples:
            >>> ParsedRepository([]).imports
            []
        """
        return [item for file in self.files for item in file.imports]

    @property
    def calls(self) -> list[Call]:
        """Access call sites across files in repository order.

        Args:
            None; access as a property on a repository.
        Returns:
            A new list containing the original Call objects, in file order.
        Raises:
            None for valid repository records.
        Examples:
            >>> ParsedRepository([]).calls
            []
        """
        return [call for file in self.files for call in file.calls]

    @property
    def inheritances(self) -> list[Inheritance]:
        """Access unresolved base-type references across files in order.

        Args:
            None; access as a property on a repository.
        Returns:
            A new list containing the original Inheritance objects, in file order.
        Raises:
            None for valid repository records.
        Examples:
            >>> ParsedRepository([]).inheritances
            []
        """
        return [inheritance for file in self.files for inheritance in file.inheritances]


def file_key(path: str) -> str:
    """Build a file-node key without normalizing or checking the path.

    Args:
        path: File path as stored in source records, usually repository-relative.
    Returns:
        The unchanged path prefixed with ``file:``.
    Raises:
        None for a string path.
    Examples:
        >>> file_key("src/main.py")
        'file:src/main.py'
        >>> file_key("")
        'file:'
    """
    return f"file:{path}"
