"""Quantitative metrics from fresh analysis or normalized saved graph facts."""

from collections import Counter
from typing import Any, cast

from .artifact import build_dependency_views
from .cycles import CircularGroup, circular_dependencies
from .dependency_metrics import dependency_metrics
from .report_markdown import render_markdown
from ..domain.models import GraphView
from ..domain.repositories import ReportFactsDTO

__all__ = ["build_report", "build_artifact_report", "render_markdown"]

COMPLEXITY_METRICS = {
    "baseCyclomaticComplexity": "cyclomaticComplexity",
    "cyclomaticComplexity": "weightedComplexity",
    "nestedCyclomaticComplexity": "nestedDecisionPenalty",
    "loopNestedComplexity": "nestedLoops",
    "maxDecisionDepth": "maxDecisionDepth",
}
DEPENDENCY_LEVELS = {"module", "file", "type", "callable"}
CALLABLE_KINDS = {"function", "method"}


def _node_order(node: dict[str, Any]):
    return node.get("path") or "", node.get("startLine") or 0, node["stableKey"]


def _dependency_values(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]):
    views = build_dependency_views(nodes, edges)
    return {
        key: metrics
        for view in views.values()
        for key, metrics in dependency_metrics(cast(GraphView, view)).items()
    }


def _file_owner(node: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> str | None:
    current = node
    while current.get("kind") != "file":
        parent = current.get("parentStableKey")
        if parent not in lookup:
            return None
        current = lookup[parent]
    return current["stableKey"]


def _file_summaries(nodes: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summaries = {
        node["stableKey"]: {"functionCount": 0, "measuredFunctionCount": 0, "weightedComplexitySum": 0}
        for node in nodes if node.get("kind") == "file"
    }
    lookup = {node["stableKey"]: node for node in nodes}
    for node in nodes:
        if node.get("kind") not in CALLABLE_KINDS:
            continue
        owner = _file_owner(node, lookup)
        if owner is None:
            continue
        values = summaries[owner]
        values["functionCount"] += 1
        complexity = node.get("properties", {}).get("cyclomaticComplexity")
        if complexity is not None:
            values["measuredFunctionCount"] += 1
            values["weightedComplexitySum"] += complexity
    return summaries


def _measurement(node: dict[str, Any], dependencies, files) -> dict[str, Any]:
    properties = node.get("properties", {})
    kind = node.get("kind")
    metrics: dict[str, Any] = {}
    if kind == "file" or kind in CALLABLE_KINDS:
        metrics["lineCount"] = properties.get("lineCount")
    if kind in CALLABLE_KINDS:
        metrics["parameterCount"] = properties.get("parameterCount")
        metrics.update({label: properties.get(name) for name, label in COMPLEXITY_METRICS.items()})
    metrics.update(files.get(node["stableKey"], {}))
    metrics.update(dependencies.get(node["stableKey"], {}))
    return {
        "stableKey": node["stableKey"],
        "subject": node.get("qualifiedName") or node.get("name") or "Unnamed item",
        "kind": kind,
        "level": node.get("level"),
        "path": node.get("path"),
        "line": node.get("startLine"),
        "metrics": metrics,
    }


def _cycle_measurements(groups: list[CircularGroup], nodes: list[dict[str, Any]]):
    paths = {node["stableKey"]: node.get("path") for node in nodes}
    return [
        {
            "id": group["id"],
            "groupSize": len(group["nodeStableKeys"]),
            "internalDependencyCount": len({
                (edge["sourceStableKey"], edge["targetStableKey"])
                for edge in group["edges"]
            }),
            "files": sorted(paths.get(key) or "Unknown file" for key in group["nodeStableKeys"]),
            "exampleCycle": [paths.get(key) or "Unknown file" for key in group["exampleCycle"]],
        }
        for group in groups
    ]


def build_artifact_report(artifact: dict[str, Any]) -> dict[str, Any]:
    """Report raw values, including zeros and unavailable metrics, without policy."""
    nodes = artifact.get("nodes", [])
    edges = artifact.get("edges", [])
    cycles = artifact.get("circularDependencies") or circular_dependencies(nodes, edges)
    dependencies = _dependency_values(nodes, edges)
    files = _file_summaries(nodes)
    levels = Counter(node.get("level") for node in nodes)
    diagnostics = artifact.get("diagnostics", [])
    return {
        "summary": {
            "files": levels["file"], "modules": levels["module"],
            "types": levels["type"], "callables": levels["callable"],
            "circularImportGroups": len(cycles["groups"]), "parseErrors": len(diagnostics),
        },
        "nodes": [
            _measurement(node, dependencies, files)
            for node in sorted(nodes, key=_node_order)
            if node.get("level") in DEPENDENCY_LEVELS or node.get("kind") in CALLABLE_KINDS
        ],
        "circularImports": _cycle_measurements(cycles["groups"], nodes),
        "diagnostics": diagnostics,
    }


def build_report(graph: ReportFactsDTO) -> dict[str, Any]:
    """Use the same projection and metric calculations on normalized saved facts."""
    nodes = []
    for record in graph.nodes:
        values = record.model_dump()
        metric_names = (*COMPLEXITY_METRICS, "lineCount", "parameterCount")
        nodes.append({**values, "properties": {name: values.get(name) for name in metric_names}})
    return build_artifact_report({
        "nodes": nodes,
        "edges": [edge.model_dump() for edge in graph.edges or graph.imports],
        "diagnostics": graph.diagnostics,
    })
