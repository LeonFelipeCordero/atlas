"""Reports measure every item without thresholds or good/bad judgments."""

from copy import deepcopy
from dataclasses import dataclass

import pytest

from atlas.domain.repositories import ReportFactsDTO, ReportImportDTO, ReportNodeDTO
from atlas.metrics.report import build_artifact_report, build_report, render_markdown


@dataclass(frozen=True)
class Complexity:
    total: int = 8
    loops: int = 0
    depth: int = 3


def callable_node(name: str, complexity: Complexity = Complexity()):
    total, loops, depth = complexity.total, complexity.loops, complexity.depth
    return {
        "stableKey": f"symbol:{name}", "name": name, "qualifiedName": f"App.{name}",
        "kind": "function", "type": "function", "level": "callable", "path": "app.py", "startLine": 10,
        "parentStableKey": "file:app.py",
        "properties": {
            "lineCount": 4, "parameterCount": 1,
            "baseCyclomaticComplexity": total - loops,
            "nestedCyclomaticComplexity": 0, "loopNestedComplexity": loops,
            "cyclomaticComplexity": total, "maxDecisionDepth": depth,
        },
    }


def file_node(path: str):
    return {
        "stableKey": f"file:{path}", "name": path, "kind": "file", "type": "file",
        "level": "file", "path": path, "parentStableKey": None, "properties": {"lineCount": 10},
    }


def test_report_contains_below_and_above_thresholds_and_keeps_input() -> None:
    artifact = {"nodes": [file_node("app.py"), callable_node("simple", Complexity(total=1, depth=0)), callable_node("complex", Complexity(total=10, loops=2))]}
    original = deepcopy(artifact)
    report = build_artifact_report(artifact)
    assert set(report) == {"summary", "nodes", "circularImports", "diagnostics", "mutationCandidates", "mutationCandidateDiagnostics"}
    measurements = {node["subject"]: node["metrics"] for node in report["nodes"]}
    assert measurements["App.simple"]["weightedComplexity"] == 1
    assert measurements["App.complex"]["cyclomaticComplexity"] == 8
    assert measurements["App.complex"]["weightedComplexity"] == 10
    assert measurements["App.complex"]["nestedLoops"] == 2
    assert measurements["app.py"]["weightedComplexitySum"] == 11
    assert measurements["app.py"]["functionCount"] == measurements["app.py"]["measuredFunctionCount"] == 2
    assert measurements["app.py"]["instability"] is None
    assert report["summary"]["callables"] == 2
    markdown = render_markdown(report)
    assert "maximum" not in markdown and "limit" not in markdown and "finding" not in markdown.lower()
    assert "Cyclomatic complexity" in markdown and "Weighted complexity" in markdown
    assert artifact == original


@pytest.mark.parametrize("type_only", [False, True])
def test_cycles_have_quantitative_counts_and_readable_paths(type_only: bool) -> None:
    nodes = [file_node(path) for path in ("a.py", "b.py")]
    edges = [
        {"sourceStableKey": f"file:{source}", "targetStableKey": f"file:{target}",
         "type": "IMPORTS", "path": source, "line": 1, "evidence": "import",
         "confidence": "INFERRED", "typeOnly": type_only}
        for source, target in (("a.py", "b.py"), ("a.py", "b.py"), ("b.py", "a.py"))
    ]
    report = build_artifact_report({"nodes": nodes, "edges": edges})
    assert report["summary"]["circularImportGroups"] == int(not type_only)
    assert all(node["metrics"]["transitiveChangeImpact"] == 1 for node in report["nodes"])
    assert all(node["metrics"]["instability"] == 0.5 for node in report["nodes"])
    if not type_only:
        group = report["circularImports"][0]
        assert group["groupSize"] == group["internalDependencyCount"] == 2
        assert group["files"] == ["a.py", "b.py"]
        assert group["exampleCycle"] == ["a.py", "b.py", "a.py"]
        assert "file:a.py" not in render_markdown(report)


def test_empty_graph_still_has_quantitative_summary() -> None:
    report = build_artifact_report({})
    assert report == {
        "summary": {"files": 0, "modules": 0, "types": 0, "callables": 0, "circularImportGroups": 0, "parseErrors": 0},
        "nodes": [], "circularImports": [], "diagnostics": [],
        "mutationCandidates": [], "mutationCandidateDiagnostics": [],
    }
    assert "files: 0" in render_markdown(report)


def test_unavailable_metrics_and_partial_file_totals_are_explicit() -> None:
    unknown = {**callable_node("unknown"), "properties": {}}
    report = build_artifact_report({"nodes": [file_node("app.py"), callable_node("known", Complexity(total=2)), unknown]})
    measurements = {node["subject"]: node["metrics"] for node in report["nodes"]}
    assert measurements["App.unknown"]["parameterCount"] is None
    assert measurements["app.py"]["functionCount"] == 2
    assert measurements["app.py"]["measuredFunctionCount"] == 1
    assert measurements["app.py"]["weightedComplexitySum"] == 2
    assert "N/A" in render_markdown(report)


def test_measurements_sort_by_path_line_then_symbol() -> None:
    nodes = [
        {**callable_node("z", Complexity(total=9)), "path": "z.py", "startLine": 1},
        {**callable_node("a", Complexity(total=9)), "startLine": 20},
        callable_node("b", Complexity(total=9)),
    ]
    report = build_artifact_report({"nodes": nodes})
    assert [node["subject"] for node in report["nodes"]] == ["App.b", "App.a", "App.z"]


def test_markdown_preserves_literal_names_and_shows_analysis_diagnostics() -> None:
    node = {**callable_node("`odd|name`"), "path": None, "startLine": None}
    report = build_artifact_report({"nodes": [node], "diagnostics": [{"path": "bad.py", "message": "Parse failed"}]})
    markdown = render_markdown(report)
    assert "`` App.`odd\\|name` ``" in markdown
    assert "Unknown file" in markdown and "None" not in markdown
    assert "Parse failed" in markdown
    assert report["summary"]["parseErrors"] == 1


def test_imports_only_normalized_facts_preserve_cycle_metrics() -> None:
    nodes = [ReportNodeDTO.model_validate(file_node(path)) for path in ("a.py", "b.py")]
    imports = [ReportImportDTO(
        sourceStableKey=f"file:{source}", targetStableKey=f"file:{target}", type="IMPORTS",
        confidence="INFERRED", path=source, line=1, evidence="import", typeOnly=False,
    ) for source, target in (("a.py", "b.py"), ("b.py", "a.py"))]
    measured = build_report(ReportFactsDTO(graphRevision="legacy", nodes=nodes, imports=imports))
    assert measured["summary"]["circularImportGroups"] == 1
    assert measured["circularImports"][0]["groupSize"] == 2
    assert all(node["metrics"]["instability"] == 0.5 for node in measured["nodes"])
