"""Findings-only reports from in-memory or saved analysis."""

from collections.abc import Mapping
from typing import Any

from .cycles import circular_dependencies
from ..domain.repositories import ReportFactsDTO

THRESHOLDS = {
    "cyclomaticComplexity": 8,
    "loopNestedComplexity": 0,
    "maxDecisionDepth": 3,
}
METRIC_LABELS = {
    "cyclomaticComplexity": "Cyclomatic complexity",
    "loopNestedComplexity": "Nested-loop count",
    "maxDecisionDepth": "Decision nesting depth",
}


def _node_order(node: dict[str, Any]):
    return node.get("path") or "", node.get("startLine") or 0, node["stableKey"]


def _metric_details(
    properties: dict[str, Any],
    thresholds: dict[str, int] = THRESHOLDS,
    labels: dict[str, str] = METRIC_LABELS,
) -> list[str]:
    return [
        f"{labels[metric]} is {properties[metric]} (limit: {threshold})."
        for metric, threshold in thresholds.items()
        if properties.get(metric) is not None and properties[metric] > threshold
    ]


def _complexity_finding(node: dict[str, Any]) -> dict[str, Any] | None:
    if node.get("kind") not in ("function", "method"):
        return None
    details = _metric_details(node.get("properties", {}))
    if not details:
        return None
    return {
        "type": "complexity",
        "subject": node.get("qualifiedName") or node.get("name") or "Unnamed callable",
        "files": [{"path": node.get("path"), "line": node.get("startLine")}],
        "details": details,
    }


def _complexity_findings(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = map(_complexity_finding, sorted(nodes, key=_node_order))
    return [finding for finding in findings if finding is not None]


def _size_details(node: dict[str, Any]) -> list[str]:
    file = node["kind"] == "file"
    thresholds = {"lineCount": 600} if file else {"lineCount": 100, "parameterCount": 7}
    labels = {"lineCount": "File line count" if file else "Function line count", "parameterCount": "Parameter count"}
    return _metric_details(node.get("properties", {}), thresholds, labels)


def _size_finding(node: dict[str, Any]) -> dict[str, Any] | None:
    kind = node.get("kind")
    if kind not in {"file", "function", "method"}:
        return None
    details = _size_details(node)
    if not details:
        return None
    location = {"path": node.get("path")}
    if kind != "file":
        location["line"] = node.get("startLine")
    return {
        "type": "size",
        "subject": node.get("qualifiedName") or node.get("name") or "Unnamed item",
        "files": [location],
        "details": details,
    }


def _size_findings(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = map(_size_finding, sorted(nodes, key=_node_order))
    return [finding for finding in findings if finding is not None]


def _cycle_files(group: dict[str, Any], paths: dict[str, Any]):
    return sorted(
        ({"path": paths.get(key)} for key in group["nodeStableKeys"]),
        key=lambda file: file["path"] or "",
    )


def _cycle_path(group: dict[str, Any], paths: dict[str, Any]) -> str:
    return " → ".join(paths.get(key) or "Unknown file" for key in group["exampleCycle"])


def _cycle_finding(group: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "circular_dependency",
        "subject": "Circular imports",
        "files": _cycle_files(group, paths),
        "details": [
            "These files form a circular import dependency.",
            f"Example cycle: {_cycle_path(group, paths)}.",
        ],
    }


def _cycle_findings(cycles: Mapping[str, Any], nodes: list[dict[str, Any]]):
    paths = {node["stableKey"]: node.get("path") for node in nodes}
    return [_cycle_finding(group, paths) for group in cycles["groups"]]


def build_report(graph: ReportFactsDTO) -> dict[str, Any]:
    """Build findings from focused normalized metrics and import-cycle facts."""
    nodes = [_report_node(node.model_dump()) for node in graph.nodes]
    cycles = circular_dependencies(nodes, [edge.model_dump() for edge in graph.imports])
    return {"findings": _complexity_findings(nodes) + _size_findings(nodes) + _cycle_findings(cycles, nodes)}


def _report_node(node: dict[str, Any]) -> dict[str, Any]:
    metrics = (*THRESHOLDS, "lineCount", "parameterCount")
    return {**node, "properties": {name: node[name] for name in metrics}}


def build_artifact_report(artifact: dict[str, Any]) -> dict[str, Any]:
    """Build the same findings from analysis without requiring persistence."""
    nodes = artifact.get("nodes", [])
    cycles = artifact.get("circularDependencies")
    if cycles is None:
        cycles = circular_dependencies(nodes, artifact.get("edges", []))
    return {"findings": _complexity_findings(nodes) + _size_findings(nodes) + _cycle_findings(cycles, nodes)}


def _code(value: str) -> str:
    """Keep source names literal even when they contain Markdown delimiters."""
    value = value.replace("\n", " ").replace("\r", " ")
    fence = "`"
    while fence in value:
        fence += "`"
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{padding}{value}{padding}{fence}"


def _location(file: dict[str, Any]) -> str:
    location = file["path"] or "Unknown file"
    if file.get("line") is not None:
        location += f":{file['line']}"
    return f"- {_code(location)}"


def _markdown_section(finding: dict[str, Any]) -> str:
    title = {"complexity": "Complexity", "size": "Size", "circular_dependency": "Circular dependency"}[finding["type"]]
    locations = map(_location, finding["files"])
    details = (f"- {detail}" for detail in finding["details"])
    return "\n".join([
        f"## {title}: {_code(finding['subject'])}",
        "", "Files:", *locations,
        "", "Findings:", *details,
    ])


def render_markdown(report: dict[str, Any]) -> str:
    """Use the same short section structure for humans and LLMs."""
    if not report["findings"]:
        return "No findings."
    return "\n\n".join(map(_markdown_section, report["findings"]))
