"""Small graph scenarios for CLI contract tests."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlas.domain.models import Diagnostic, GraphEdge, GraphNode
from atlas.metrics.artifact import GraphArtifact


def _properties(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in (defaults | overrides).items() if value is not None}


def _nodes(options: dict[str, Any]) -> list[GraphNode]:
    return [
        {
            "stableKey": "file:café.py", "type": "file", "kind": "file", "level": "file",
            "language": "python", "name": "café.py", "qualifiedName": "café.py",
            "path": "café.py", "parentStableKey": None, "depth": 0, "ancestorStableKeys": [],
            "properties": _properties({"lineCount": 600}, options.get("file_metrics", {})),
        },
        {
            "stableKey": "function:brew", "type": "function", "kind": "function", "level": "callable",
            "language": "python", "name": "brew", "qualifiedName": "café.brew",
            "path": "café.py", "parentStableKey": "file:café.py", "startLine": 2,
            "depth": 1, "ancestorStableKeys": ["file:café.py"],
            "properties": _properties({
                "lineCount": 100, "parameterCount": 3, "baseCyclomaticComplexity": 5,
                "cyclomaticComplexity": 8, "nestedCyclomaticComplexity": 3,
                "loopNestedComplexity": 0, "maxDecisionDepth": 3,
            }, options.get("function_metrics", {})),
        },
    ]


def make_artifact(root: Path, **options: Any) -> dict[str, Any]:
    nodes = _nodes(options)
    diagnostics: list[Diagnostic] = options.get("diagnostics", [])
    edges: list[GraphEdge] = []
    if options.get("circular_imports", False):
        nodes.append({
            **nodes[0], "stableKey": "file:tea.py", "name": "tea.py",
            "qualifiedName": "tea.py", "path": "tea.py",
        })
        edges = [
            {"sourceStableKey": f"file:{source}", "targetStableKey": f"file:{target}",
             "type": "IMPORTS", "confidence": "EXTRACTED", "path": source, "line": 1,
             "evidence": "import", "sourceType": "file", "sourceKind": "file", "sourceLevel": "file",
             "targetType": "file", "targetKind": "file", "targetLevel": "file"}
            for source, target in [("café.py", "tea.py"), ("tea.py", "café.py")]
        ]
    if options.get("empty", False):
        nodes, edges = [], []
    files = sum(node["type"] == "file" for node in nodes)
    callables = sum(node["type"] == "function" for node in nodes)
    return asdict(GraphArtifact(
        schemaVersion=2, repository={"path": str(root), "name": "café"},
        stats={"files": files, "symbols": callables, "modules": 0, "types": 0, "callables": callables,
               "nodes": len(nodes), "edges": len(edges), "externalNodes": 0,
               "parseErrors": len(diagnostics)},
        nodes=nodes, edges=edges, views={}, diagnostics=diagnostics,
    ))
