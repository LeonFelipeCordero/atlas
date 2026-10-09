"""Build and validate in-memory version-2 repository graph artifacts."""
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from pydantic import NonNegativeInt, model_validator
from pydantic.dataclasses import dataclass
from typing_extensions import Self

from .cycles import CircularDependencies, circular_dependencies
from .dependency_metrics import METRIC_NAMES, dependency_metrics
from .models import ParsedRepository, file_key
from .resolver import ResolvedGraph
from .models import (
    MODEL_CONFIG,
    Diagnostic,
    GraphEdge,
    GraphNode,
    GraphView,
    RepositoryMetadata,
)


@dataclass(config=MODEL_CONFIG)
class GraphArtifact:
    """Strict graph payload with unique node keys and valid parent/edge references.

    Construction and assignment validate fields; in-place container edits require
    ``validate_artifact``. Reference checks do not cover views or cycle groups.
    """

    schemaVersion: Literal[2]
    repository: RepositoryMetadata
    stats: dict[str, NonNegativeInt]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    views: dict[str, GraphView]
    diagnostics: list[Diagnostic]
    circularDependencies: CircularDependencies | None = None

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Check references and optional dependency counts, returning this instance.

        Runs automatically after model validation; call directly to check node
        uniqueness, references and dependency counts after editing containers.
        This does not revalidate all field schemas.

        Args:
            None. Uses this artifact's nodes and edges.
        Returns:
            This artifact, unchanged.
        Raises:
            ValueError: Duplicate keys, missing references, or invalid dependency counts.
            KeyError: Required reference fields were removed by in-place edits.

        Examples:
            >>> artifact = build_artifact(Path("repo"), ParsedRepository([]), ResolvedGraph([], []))
            >>> artifact.validate_references() is artifact
            True
        """
        keys = [node["stableKey"] for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("Graph artifact contains duplicate stable node keys")
        known_keys = set(keys)
        for node in self.nodes:
            _validate_dependency_metrics(node)
            parent_key = node["parentStableKey"]
            if parent_key and parent_key not in known_keys:
                raise ValueError(f"Graph node references missing parent: {parent_key}")
        for edge in self.edges:
            _validate_edge_endpoints(edge, known_keys)
        return self


def _validate_dependency_metrics(node: GraphNode) -> None:
    for name in METRIC_NAMES:
        if name not in node["properties"]:
            continue
        value = node["properties"][name]
        if type(value) is not int or value < 0:
            raise ValueError(f"Node property {name} must be a nonnegative integer")


def _validate_edge_endpoints(edge: GraphEdge, known_keys: set[str]) -> None:
    for endpoint, key in (
        ("source", edge["sourceStableKey"]),
        ("target", edge["targetStableKey"]),
    ):
        if key not in known_keys:
            raise ValueError(f"Graph edge references missing {endpoint}: {key}")


def _module_key(path: str) -> str:
    return f"module:{path}"


def _symbol_level(kind: str) -> str:
    if kind in {"module", "namespace", "package"}:
        return "module"
    if kind in {"class", "enum", "interface", "struct", "trait", "type"}:
        return "type"
    if kind in {"constructor", "function", "method", "procedure"}:
        return "callable"
    return "symbol"


def _directory_ancestors(path: str) -> set[str]:
    paths = set()
    parent = PurePosixPath(path).parent
    while parent.as_posix() != ".":
        paths.add(parent.as_posix())
        parent = parent.parent
    return paths


def _module_paths(repository: ParsedRepository) -> list[str]:
    paths = {"."}
    for file in repository.files:
        paths.update(_directory_ancestors(file.source.path))
    return sorted(paths, key=lambda path: (path.count("/"), path))


def _containment_edge(
    source_key: str, target_key: str, path: str, line: int, evidence: str | None = None
) -> dict[str, object]:
    return {
        "sourceStableKey": source_key,
        "targetStableKey": target_key,
        "type": "CONTAINS",
        "confidence": "EXTRACTED",
        "path": path,
        "line": line,
        "evidence": evidence,
    }


def _ancestor_keys(
    node: dict[str, object], nodes_by_key: dict[str, dict[str, object]]
) -> list[str]:
    ancestors = []
    parent_key = node.get("parentStableKey")
    while parent_key:
        ancestors.append(str(parent_key))
        parent = nodes_by_key.get(str(parent_key))
        parent_key = parent.get("parentStableKey") if parent else None
    return ancestors


def _add_hierarchy(nodes: list[dict[str, object]]) -> None:
    nodes_by_key = {str(node["stableKey"]): node for node in nodes}
    for node in nodes:
        ancestors = _ancestor_keys(node, nodes_by_key)
        node["depth"] = len(ancestors)
        node["ancestorStableKeys"] = list(reversed(ancestors))


def _enrich_edges(
    edges: list[dict[str, object]], nodes: list[dict[str, object]]
) -> None:
    nodes_by_key = {node["stableKey"]: node for node in nodes}
    for edge in edges:
        source = nodes_by_key[edge["sourceStableKey"]]
        target = nodes_by_key[edge["targetStableKey"]]
        edge["sourceType"] = source["type"]
        edge["sourceKind"] = source["kind"]
        edge["sourceLevel"] = source["level"]
        edge["targetType"] = target["type"]
        edge["targetKind"] = target["kind"]
        edge["targetLevel"] = target["level"]


def _projected_key(
    node_key: str, level: str, nodes_by_key: dict[str, dict[str, object]]
) -> str | None:
    current = nodes_by_key.get(node_key)
    while current:
        if current["level"] == level:
            return str(current["stableKey"])
        parent_key = current.get("parentStableKey")
        current = nodes_by_key.get(str(parent_key)) if parent_key else None
    return None


def _projected_relationships(
    edges: list[dict[str, object]],
    level: str,
    nodes_by_key: dict[str, dict[str, object]],
) -> dict[tuple[str, str], list[dict[str, object]]]:
    relationships: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for edge in edges:
        if edge["type"] == "CONTAINS":
            continue
        source = _projected_key(str(edge["sourceStableKey"]), level, nodes_by_key)
        target = _projected_key(str(edge["targetStableKey"]), level, nodes_by_key)
        if not source or not target or source == target:
            continue
        relationships[source, target].append(edge)
    return relationships


def _relationship_counts(edges: list[dict[str, object]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(edge[field]) for edge in edges).items()))


def _view_edges(
    relationships: dict[tuple[str, str], list[dict[str, object]]], level: str
) -> list[dict[str, object]]:
    projected: list[dict[str, object]] = []
    for (source, target), edges in sorted(relationships.items()):
        projected.append(
            {
                "sourceStableKey": source,
                "targetStableKey": target,
                "type": "DEPENDS_ON",
                "level": level,
                "count": len(edges),
                "relationshipCounts": _relationship_counts(edges, "type"),
                "confidenceCounts": _relationship_counts(edges, "confidence"),
            }
        )
    return projected


def _level_view(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    level: str,
    nodes_by_key: dict[str, dict[str, object]],
) -> dict[str, Any]:
    relationships = _projected_relationships(edges, level, nodes_by_key)
    return {
        "nodes": [node["stableKey"] for node in nodes if node["level"] == level],
        "edges": _view_edges(relationships, level),
    }


def _build_views(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> dict[str, dict[str, Any]]:
    nodes_by_key = {str(node["stableKey"]): node for node in nodes}
    return {
        level: _level_view(nodes, edges, level, nodes_by_key)
        for level in ("module", "file", "type", "callable")
    }


def _add_view_metrics(
    view: dict[str, Any], nodes_by_key: dict[str, dict[str, object]]
) -> None:
    for key, metrics in dependency_metrics(cast(GraphView, view)).items():
        cast(dict[str, object], nodes_by_key[key]["properties"]).update(metrics)


def _add_dependency_metrics(
    nodes: list[dict[str, object]], views: dict[str, dict[str, Any]]
) -> None:
    nodes_by_key = {str(node["stableKey"]): node for node in nodes}
    for view in views.values():
        _add_view_metrics(view, nodes_by_key)


def _add_directory_nodes(
    root: Path,
    repository: ParsedRepository,
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> None:
    for path in _module_paths(repository):
        parent_path = PurePosixPath(path).parent.as_posix()
        parent_key = "repository" if path == "." else _module_key(parent_path)
        name = root.name if path == "." else PurePosixPath(path).name
        nodes.append(
            {
                "stableKey": _module_key(path),
                "type": "module",
                "kind": "directory",
                "level": "module",
                "language": None,
                "name": name,
                "qualifiedName": root.name if path == "." else path.replace("/", "."),
                "path": path,
                "parentStableKey": parent_key,
                "properties": {},
            }
        )
        edges.append(_containment_edge(parent_key, _module_key(path), path, 1))


def _add_file_nodes(
    repository: ParsedRepository,
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    diagnostics: list[dict[str, object]],
) -> None:
    for file in repository.files:
        source = file.source
        parent_key = _module_key(PurePosixPath(source.path).parent.as_posix())
        nodes.append(
            {
                "stableKey": file_key(source.path),
                "type": "file",
                "kind": "file",
                "level": "file",
                "language": source.language,
                "name": source.absolute_path.name,
                "qualifiedName": source.path,
                "path": source.path,
                "parentStableKey": parent_key,
                "properties": {
                    "bytes": len(source.source),
                    "lineCount": source.source.count(b"\n")
                    + int(bool(source.source) and not source.source.endswith(b"\n")),
                    "sha256": file.content_hash,
                },
            }
        )
        edges.append(
            _containment_edge(parent_key, file_key(source.path), source.path, 1)
        )
        if file.parse_error:
            diagnostics.append(
                {
                    "severity": "error",
                    "path": source.path,
                    "language": source.language,
                    "message": file.parse_error,
                }
            )


def _add_symbol_nodes(
    repository: ParsedRepository,
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> None:
    for symbol in repository.symbols:
        level = _symbol_level(symbol.kind)
        nodes.append(
            {
                "stableKey": symbol.key,
                "type": symbol.kind,
                "kind": symbol.kind,
                "level": level,
                "language": symbol.language,
                "name": symbol.name,
                "qualifiedName": symbol.qualified_name,
                "path": symbol.file_path,
                "parentStableKey": symbol.parent_key,
                "startLine": symbol.start_line,
                "startColumn": symbol.start_column,
                "endLine": symbol.end_line,
                "endColumn": symbol.end_column,
                "signature": symbol.signature,
                "properties": {
                    "visibility": symbol.visibility,
                    "decorators": symbol.decorators,
                    **(
                        {"lineCount": symbol.line_count}
                        if symbol.line_count is not None else {}
                    ),
                    **(
                        {"parameterCount": symbol.parameter_count}
                        if symbol.parameter_count is not None else {}
                    ),
                    **(
                        asdict(symbol.complexity)
                        if symbol.complexity is not None
                        else {}
                    ),
                },
            }
        )
        edges.append(
            _containment_edge(
                symbol.parent_key,
                symbol.key,
                symbol.file_path,
                symbol.start_line,
                f"{symbol.parent_key} contains {symbol.name}",
            )
        )


def _add_external_nodes(graph: ResolvedGraph, nodes: list[dict[str, object]]) -> None:
    for external in graph.external_nodes:
        nodes.append(
            {
                "stableKey": external.key,
                "type": "external",
                "kind": external.kind,
                "level": "external",
                "language": external.language,
                "name": external.name.split(".")[-1],
                "qualifiedName": f"external:{external.language}:{external.name}",
                "path": None,
                "parentStableKey": "repository",
                "properties": {},
            }
        )


def build_artifact(
    root: Path, repository: ParsedRepository, graph: ResolvedGraph
) -> GraphArtifact:
    """Assemble a validated graph from parsed sources and resolved relationships.

    Use after resolution; this adds hierarchy, dependency views, diagnostics,
    dependency metrics, import-cycle groups, and a UTC indexing timestamp without
    reading files.

    Args:
        root: Repository path used for names and metadata, without normalization.
        repository: Parsed files and their symbols.
        graph: Resolved connections and external nodes.
    Returns:
        A version-2 artifact with statistics and enriched nodes/edges.
    Raises:
        KeyError: A parent or connection endpoint is absent during enrichment.
        pydantic.ValidationError: Generated fields or references fail validation.

    Examples:
        >>> build_artifact(Path("repo"), ParsedRepository([]), ResolvedGraph([], [])).stats["files"]
        0
    """
    nodes: list[dict[str, object]] = [
        {
            "stableKey": "repository",
            "type": "repository",
            "kind": "repository",
            "level": "repository",
            "language": None,
            "name": root.name,
            "qualifiedName": root.name,
            "path": ".",
            "parentStableKey": None,
            "properties": {"absolutePath": str(root)},
        }
    ]
    edges = []
    diagnostics = []
    _add_directory_nodes(root, repository, nodes, edges)
    _add_file_nodes(repository, nodes, edges, diagnostics)
    _add_symbol_nodes(repository, nodes, edges)
    _add_external_nodes(graph, nodes)
    edges.extend(
        {
            "sourceStableKey": edge.source_key,
            "targetStableKey": edge.target_key,
            "type": edge.type,
            "confidence": edge.confidence,
            "path": edge.path,
            "line": edge.line,
            "evidence": edge.evidence,
            **({"typeOnly": True} if edge.type_only else {}),
        }
        for edge in graph.connections
    )
    _add_hierarchy(nodes)
    _enrich_edges(edges, nodes)
    views = _build_views(nodes, edges)
    _add_dependency_metrics(nodes, views)
    level_counts = {level: len(view["nodes"]) for level, view in views.items()}
    return GraphArtifact(
        2,
        {
            "path": str(root),
            "name": root.name,
            "indexedAt": datetime.now(timezone.utc).isoformat(),
            "languages": sorted({file.source.language for file in repository.files}),
        },
        {
            "files": len(repository.files),
            "symbols": len(repository.symbols),
            "modules": level_counts["module"],
            "types": level_counts["type"],
            "callables": level_counts["callable"],
            "nodes": len(nodes),
            "edges": len(edges),
            "externalNodes": len(graph.external_nodes),
            "parseErrors": len(diagnostics),
        },
        cast(list[GraphNode], nodes),
        cast(list[GraphEdge], edges),
        cast(dict[str, GraphView], views),
        cast(list[Diagnostic], diagnostics),
        circular_dependencies(nodes, edges),
    )


def validate_artifact(artifact: GraphArtifact) -> None:
    """Revalidate a snapshot, including changes made inside lists and dictionaries.

    Use before consuming an artifact that may have been mutated in place.

    Args:
        artifact: Artifact to check without modifying it.
    Returns:
        None when the snapshot satisfies the schema and reference checks.
    Raises:
        pydantic.ValidationError: Invalid fields, duplicate keys, or missing references.

    Examples:
        >>> artifact = build_artifact(Path("repo"), ParsedRepository([]), ResolvedGraph([], []))
        >>> validate_artifact(artifact)
    """
    # Revalidate a snapshot: in-place list/dict edits bypass assignment validation.
    GraphArtifact(**asdict(artifact))
