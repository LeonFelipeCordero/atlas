"""Explicit artifact-to-row conversion; no sessions, entities, or database calls."""

from typing import Any

METRIC_NAMES = (
    "lineCount", "parameterCount", "baseCyclomaticComplexity",
    "nestedCyclomaticComplexity", "loopNestedComplexity", "cyclomaticComplexity",
    "maxDecisionDepth",
)
POSITIONS = ("startLine", "startColumn", "endLine", "endColumn")


def _properties(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("properties") or {}


def _decorators(node: dict[str, Any]) -> list[str]:
    return _properties(node).get("decorators") or []


def validate_collections(artifact: dict[str, Any]) -> None:
    for name in ("nodes", "edges", "diagnostics"):
        if name in artifact and not isinstance(artifact[name], list):
            raise ValueError("Graph artifact collections must be arrays")
    for node in artifact.get("nodes", []):
        decorators = _properties(node).get("decorators")
        if decorators is not None and not isinstance(decorators, list):
            raise ValueError("Graph decorators must be arrays or null")


def validate_parentage(artifact: dict[str, Any]) -> None:
    """Reject ambiguous occurrence containers and cycles; foreign keys check references."""
    validate_collections(artifact)
    parents = {node["stableKey"]: node.get("parentStableKey") for node in artifact.get("nodes", [])}
    complete: set[str] = set()
    for key in parents:
        _validate_ancestry(key, parents, complete)


def _validate_ancestry(key: str, parents: dict[str, str | None], complete: set[str]) -> None:
    chain: set[str] = set()
    current: str | None = key
    while current is not None and current in parents and current not in complete:
        if current in chain:
            raise ValueError(f"Graph node has cyclic parentage: {current}")
        chain.add(current)
        current = parents[current]
    complete.update(chain)


def graph_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    repository = artifact.get("repository") or {}
    return {
        "schema_version": artifact.get("schemaVersion"),
        "indexed_at": repository.get("indexedAt"),
        "root_name": repository.get("name"),
        "root_path": repository.get("path"),
    }


def node_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repository_id": repository_id,
            "node_key": node["stableKey"],
            "parent_key": node.get("parentStableKey"),
            "ordinal": ordinal,
            "type": node["type"],
            "kind": node["kind"],
            "level": node["level"],
            "language": node.get("language"),
            "name": node["name"],
            "qualified_name": node.get("qualifiedName"),
            "path": node.get("path"),
        }
        for ordinal, node in enumerate(artifact.get("nodes", []))
    ]


def file_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repository_id": repository_id,
            "node_key": node["stableKey"],
            "byte_count": _properties(node).get("bytes"),
            "sha256": _properties(node).get("sha256"),
        }
        for node in artifact.get("nodes", []) if node["level"] == "file"
    ]


def is_symbol(node: dict[str, Any]) -> bool:
    properties = _properties(node)
    return (
        node["level"] in {"type", "callable", "symbol"}
        or node["level"] == "module" and node["kind"] not in {"directory", "folder"}
        or "signature" in node or any(name in node for name in POSITIONS)
        or "visibility" in properties or "decorators" in properties
    )


def symbol_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repository_id": repository_id,
            "node_key": node["stableKey"],
            "start_line": node.get("startLine"),
            "start_column": node.get("startColumn"),
            "end_line": node.get("endLine"),
            "end_column": node.get("endColumn"),
            "signature": node.get("signature"),
            "visibility": _properties(node).get("visibility"),
        }
        for node in artifact.get("nodes", []) if is_symbol(node)
    ]


def decorator_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"repository_id": repository_id, "node_key": node["stableKey"], "ordinal": ordinal, "decorator": decorator}
        for node in artifact.get("nodes", []) if is_symbol(node)
        for ordinal, decorator in enumerate(_decorators(node))
    ]


def _metric_record(repository_id: str, node: dict[str, Any]) -> dict[str, Any]:
    properties = _properties(node)
    return {
        "repository_id": repository_id,
        "node_key": node["stableKey"],
        "line_count": properties.get("lineCount"),
        "parameter_count": properties.get("parameterCount"),
        "base_complexity": properties.get("baseCyclomaticComplexity"),
        "nested_complexity": properties.get("nestedCyclomaticComplexity"),
        "loop_complexity": properties.get("loopNestedComplexity"),
        "total_complexity": properties.get("cyclomaticComplexity"),
        "max_decision_depth": properties.get("maxDecisionDepth"),
    }


def metric_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _metric_record(repository_id, node)
        for node in artifact.get("nodes", [])
        if any(name in _properties(node) for name in METRIC_NAMES)
    ]


def edge_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repository_id": repository_id,
            "ordinal": ordinal,
            "source_key": edge["sourceStableKey"],
            "target_key": edge["targetStableKey"],
            "relationship": edge["type"],
            "confidence": edge["confidence"],
            "path": edge.get("path"),
            "line": edge.get("line"),
            "evidence": edge.get("evidence"),
            "type_only": edge.get("typeOnly") is True,
        }
        for ordinal, edge in enumerate(artifact.get("edges", []))
    ]


def diagnostic_records(repository_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repository_id": repository_id,
            "ordinal": ordinal,
            "severity": diagnostic["severity"],
            "path": diagnostic["path"],
            "language": diagnostic["language"],
            "message": diagnostic["message"],
        }
        for ordinal, diagnostic in enumerate(artifact.get("diagnostics", []))
    ]
