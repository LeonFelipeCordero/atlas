"""Threshold boundaries, findings-only output, and legacy snapshot reporting."""

from copy import deepcopy

import pytest

from atlas.domain.report import build_report, render_markdown
from atlas.domain.repositories import GraphDTO


def callable_node(name: str, total: int = 8, loops: int = 0, depth: int = 3):
    return {
        "stableKey": f"symbol:{name}", "name": name, "qualifiedName": f"App.{name}",
        "kind": "function", "level": "callable", "path": "app.py", "startLine": 10,
        "depth": 9,
        "properties": {
            "baseCyclomaticComplexity": total - loops,
            "nestedCyclomaticComplexity": 0,
            "loopNestedComplexity": loops,
            "cyclomaticComplexity": total,
            "maxDecisionDepth": depth,
        },
    }


def test_strict_independent_thresholds_and_deduplication() -> None:
    nodes = [
        callable_node("boundary"),
        callable_node("total", total=9),
        callable_node("loops", total=4, loops=1, depth=2),
        callable_node("depth", total=7, depth=4),
        callable_node("all", total=10, loops=2, depth=5),
        {**callable_node("file", total=99), "kind": "file", "level": "file"},
        {**callable_node("constructor", total=99), "kind": "constructor"},
        {**callable_node("legacy"), "properties": {}},
        {**callable_node("method", total=9), "kind": "method"},
    ]
    artifact = {"nodes": nodes, "circularDependencies": {"version": 1, "groups": []}}
    original = deepcopy(artifact)
    report = build_report(GraphDTO(repositoryId="repo", artifact=artifact, importedAt=1))
    assert set(report) == {"findings"}
    findings = {finding["subject"]: finding for finding in report["findings"]}
    assert set(findings) == {f"App.{name}" for name in ("total", "loops", "depth", "all", "method")}
    for name, description in (
        ("total", "Cyclomatic complexity is 9 (limit: 8)."),
        ("loops", "Nested-loop count is 1 (limit: 0)."),
        ("depth", "Decision nesting depth is 4 (limit: 3)."),
    ):
        assert findings[f"App.{name}"]["details"] == [description]
    assert findings["App.all"] == {
        "type": "complexity", "subject": "App.all",
        "files": [{"path": "app.py", "line": 10}],
        "details": [
            "Cyclomatic complexity is 10 (limit: 8).",
            "Nested-loop count is 2 (limit: 0).",
            "Decision nesting depth is 5 (limit: 3).",
        ],
    }
    assert list(findings) == sorted(findings)
    assert artifact == original


@pytest.mark.parametrize("cycles", [None, "missing"])
def test_legacy_cycles_are_computed_from_imports_as_readable_paths(cycles) -> None:
    nodes = [{"stableKey": f"file:{path}", "type": "file", "path": path} for path in ("a.py", "b.py")]
    edges = [
        {
            "sourceStableKey": f"file:{source}", "targetStableKey": f"file:{target}",
            "type": "IMPORTS", "path": source, "line": 1,
            "evidence": f"import {target[:-3]}", "confidence": "INFERRED",
        }
        for source, target in (("a.py", "b.py"), ("b.py", "a.py"))
    ]
    artifact = {"nodes": nodes, "edges": edges, "diagnostics": [{"message": "parse error"}]}
    if cycles is None:
        artifact["circularDependencies"] = None
    report = build_report(GraphDTO(repositoryId="repo", artifact=artifact, importedAt=1))
    assert report == {"findings": [{
        "type": "circular_dependency", "subject": "Circular imports",
        "files": [{"path": "a.py"}, {"path": "b.py"}],
        "details": [
            "These files form a circular import dependency.",
            "Example cycle: a.py → b.py → a.py.",
        ],
    }]}
    assert "file:a.py" not in render_markdown(report)


def test_empty_graph_has_only_empty_findings() -> None:
    report = build_report(GraphDTO(repositoryId="repo", artifact={}, importedAt=1))
    assert report == {"findings": []}
    assert render_markdown(report) == "No findings."


def test_markdown_has_subject_location_and_only_exceeded_metrics() -> None:
    report = build_report(GraphDTO(repositoryId="repo", artifact={
        "nodes": [callable_node("total", total=9)],
    }, importedAt=1))
    assert render_markdown(report) == (
        "## Complexity: `App.total`\n\n"
        "Files:\n- `app.py:10`\n\n"
        "Findings:\n- Cyclomatic complexity is 9 (limit: 8)."
    )


def test_findings_sort_by_path_line_then_symbol() -> None:
    nodes = [
        {**callable_node("z", total=9), "path": "z.py", "startLine": 1},
        {**callable_node("a", total=9), "startLine": 20},
        callable_node("b", total=9),
    ]
    report = build_report(GraphDTO(repositoryId="repo", artifact={"nodes": nodes}, importedAt=1))
    assert [finding["subject"] for finding in report["findings"]] == ["App.b", "App.a", "App.z"]


def test_markdown_handles_missing_locations_and_literal_delimiters() -> None:
    node = {**callable_node("`odd`", total=9), "path": None, "startLine": None}
    report = build_report(GraphDTO(repositoryId="repo", artifact={"nodes": [node]}, importedAt=1))
    markdown = render_markdown(report)
    assert "`` App.`odd` ``" in markdown
    assert "- `Unknown file`" in markdown
    assert "None" not in markdown
