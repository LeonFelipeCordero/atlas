"""Report projections retain raw metrics, ownership, and saved-fact semantics."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from atlas.domain.repositories import ReportFactsDTO, ReportImportDTO, ReportNodeDTO
from atlas.metrics import report


@pytest.fixture
def boundaries(monkeypatch):
    dependencies = Mock(return_value={})
    cycles = Mock(return_value={"groups": []})
    monkeypatch.setattr(report, "_dependency_values", dependencies)
    monkeypatch.setattr(report, "circular_dependencies", cycles)
    return dependencies, cycles


def test_empty_artifact_has_exact_empty_report(boundaries):
    assert report.build_artifact_report({}) == {
        "summary": {"files": 0, "modules": 0, "types": 0, "callables": 0, "circularImportGroups": 0, "parseErrors": 0},
        "nodes": [], "circularImports": [], "diagnostics": [], "mutationCandidates": []}


def test_measurement_maps_complexity_and_preserves_zero_and_unavailable(boundaries):
    dependencies, _ = boundaries
    dependencies.return_value = {"fn": {"fanIn": 0, "instability": None}}
    node = {"stableKey": "fn", "kind": "method", "level": "callable", "name": "short",
            "qualifiedName": "Type.method", "path": "a.py", "startLine": 0,
            "properties": {"lineCount": 0, "parameterCount": 0, "baseCyclomaticComplexity": 1,
                           "cyclomaticComplexity": 7, "nestedCyclomaticComplexity": 3,
                           "loopNestedComplexity": 2, "maxDecisionDepth": 4}}

    result = report.build_artifact_report({"nodes": [node]})

    assert result["nodes"] == [{
        "stableKey": "fn", "subject": "Type.method", "kind": "method", "level": "callable", "path": "a.py", "line": 0,
        "metrics": {"lineCount": 0, "parameterCount": 0, "cyclomaticComplexity": 1, "weightedComplexity": 7,
                    "nestedDecisionPenalty": 3, "nestedLoops": 2, "maxDecisionDepth": 4, "fanIn": 0, "instability": None}}]


def test_file_summary_counts_nested_callables_but_not_orphans_or_types():
    nodes = [
        {"stableKey": "file", "kind": "file"},
        {"stableKey": "type", "kind": "class", "parentStableKey": "file"},
        {"stableKey": "zero", "kind": "method", "parentStableKey": "type", "properties": {"cyclomaticComplexity": 0}},
        {"stableKey": "measured", "kind": "function", "parentStableKey": "zero", "properties": {"cyclomaticComplexity": 8}},
        {"stableKey": "second", "kind": "function", "parentStableKey": "file", "properties": {"cyclomaticComplexity": 3}},
        {"stableKey": "missing", "kind": "function", "parentStableKey": "file"},
        {"stableKey": "orphan", "kind": "function", "parentStableKey": "absent", "properties": {"cyclomaticComplexity": 99}},
        {"stableKey": "empty", "kind": "file"},
    ]

    assert report._file_summaries(nodes) == {
        "file": {"functionCount": 4, "measuredFunctionCount": 3, "weightedComplexitySum": 11},
        "empty": {"functionCount": 0, "measuredFunctionCount": 0, "weightedComplexitySum": 0}}


def test_report_orders_by_path_line_key_filters_non_subjects_and_does_not_mutate(boundaries):
    artifact = {"nodes": [
        {"stableKey": "z", "kind": "class", "level": "type", "path": "b.py"},
        {"stableKey": "b", "kind": "function", "path": "a.py", "startLine": 2, "name": "named"},
        {"stableKey": "a", "kind": "class", "level": "type", "path": "a.py", "startLine": 2},
        {"stableKey": "root", "kind": "repository", "level": "repository"},
        {"stableKey": "module", "kind": "module", "level": "module", "path": None},
    ], "diagnostics": [{"message": "parse failed"}], "mutationCandidates": [{"kind": "binary"}]}
    before = deepcopy(artifact)

    result = report.build_artifact_report(artifact)

    assert [(n["stableKey"], n["subject"]) for n in result["nodes"]] == [
        ("module", "Unnamed item"), ("a", "Unnamed item"), ("b", "named"), ("z", "Unnamed item")]
    assert result["summary"] == {"files": 0, "modules": 1, "types": 2, "callables": 0, "circularImportGroups": 0, "parseErrors": 1}
    assert (result["diagnostics"], result["mutationCandidates"] ) == (artifact["diagnostics"], artifact["mutationCandidates"])
    assert artifact == before


def test_supplied_cycles_count_distinct_directed_pairs_and_unknown_paths(boundaries):
    _, cycles = boundaries
    artifact = {"nodes": [{"stableKey": "a", "kind": "file", "level": "file", "path": "z.py"}],
                "circularDependencies": {"groups": [{"id": "cycle", "nodeStableKeys": ["a", "b"],
                    "edges": [{"sourceStableKey": "a", "targetStableKey": "b"}] * 2 + [
                        {"sourceStableKey": "b", "targetStableKey": "a"}], "exampleCycle": ["a", "b", "a"]}]}}

    result = report.build_artifact_report(artifact)

    assert result["circularImports"] == [{"id": "cycle", "groupSize": 2, "internalDependencyCount": 2,
                                         "files": ["Unknown file", "z.py"], "exampleCycle": ["z.py", "Unknown file", "z.py"]}]
    cycles.assert_not_called()


def test_dependency_values_merges_each_projected_level(monkeypatch):
    views = {"file": {"nodes": ["file"], "edges": []}, "callable": {"nodes": ["fn"], "edges": []}}
    project = Mock(return_value=views)
    calculate = Mock(side_effect=[{"file": {"fanIn": 1}}, {"fn": {"fanOut": 2}}])
    monkeypatch.setattr(report, "build_dependency_views", project)
    monkeypatch.setattr(report, "dependency_metrics", calculate)
    nodes, edges = [{"stableKey": "file"}], [{"type": "CALLS"}]

    assert report._dependency_values(nodes, edges) == {"file": {"fanIn": 1}, "fn": {"fanOut": 2}}
    project.assert_called_once_with(nodes, edges)
    assert [entry.args[0] for entry in calculate.call_args_list] == list(views.values())


@pytest.mark.parametrize("has_edges", [False, True])
def test_saved_facts_prefers_edges_and_nests_metric_properties(monkeypatch, has_edges):
    node = ReportNodeDTO(stableKey="fn", type="Symbol", level="callable", kind="function", name="run",
                         lineCount=0, baseCyclomaticComplexity=1, cyclomaticComplexity=4)
    import_edge = ReportImportDTO(sourceStableKey="a", targetStableKey="b", type="IMPORTS", confidence="EXTRACTED",
                                  path="a.py", line=1, evidence="import b", typeOnly=True)
    call_edge = import_edge.model_copy(update={"type": "CALLS"})
    facts = ReportFactsDTO(graphRevision="rev", nodes=[node], imports=[import_edge],
                           edges=[call_edge] if has_edges else [], diagnostics=[{"message": "error"}],
                           mutationCandidates=[{"kind": "binary"}])
    project = Mock(return_value={"sentinel": True})
    monkeypatch.setattr(report, "build_artifact_report", project)

    assert report.build_report(facts) == {"sentinel": True}
    project.assert_called_once_with({
        "nodes": [{**node.model_dump(), "properties": {
            "baseCyclomaticComplexity": 1, "cyclomaticComplexity": 4, "nestedCyclomaticComplexity": None,
            "loopNestedComplexity": None, "maxDecisionDepth": None, "lineCount": 0, "parameterCount": None}}],
        "edges": [(call_edge if has_edges else import_edge).model_dump()],
        "diagnostics": [{"message": "error"}], "mutationCandidates": [{"kind": "binary"}]})
