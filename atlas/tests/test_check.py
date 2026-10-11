"""Configured limits evaluate the same quantitative report, never hidden policy."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_text
from dataclasses import asdict, dataclass
from pathlib import Path

import pytest

from atlas.indexer import analyze_repository
from atlas.metrics.check import build_check, render_check
from atlas.metrics.config import CheckConfig
from atlas.metrics.report import build_artifact_report


def disabled_config(**overrides) -> CheckConfig:
    return CheckConfig.model_validate({**dict.fromkeys(CheckConfig.model_fields), **overrides})


def report_node(kind: str, metrics: dict, level: str | None = None):
    return {"stableKey": kind, "subject": kind, "kind": kind, "level": level or kind,
            "path": "app.py", "line": 10, "metrics": metrics}


def report(nodes=None, cycles=None, diagnostics=None):
    return {"summary": {"circularImportGroups": len(cycles or [])}, "nodes": nodes or [],
            "circularImports": cycles or [], "diagnostics": diagnostics or []}


@dataclass(frozen=True)
class LimitCase:
    rule: str
    metric: str
    kind: str
    limit: int | float


@pytest.mark.parametrize("case", [
    LimitCase("maxFileLines", "lineCount", "file", 600),
    LimitCase("maxFunctionLines", "lineCount", "function", 100),
    LimitCase("maxParameters", "parameterCount", "method", 3),
    LimitCase("maxWeightedComplexity", "weightedComplexity", "function", 8),
    LimitCase("maxDecisionDepth", "maxDecisionDepth", "function", 3),
    LimitCase("maxNestedLoops", "nestedLoops", "function", 0),
    LimitCase("maxChangeImpact", "transitiveChangeImpact", "file", 2),
    LimitCase("maxInstability", "instability", "module", 0.5),
], ids=lambda case: case.rule)
def test_equality_passes_and_only_exceeded_limits_are_returned(case: LimitCase) -> None:
    rule, metric, kind, limit = case.rule, case.metric, case.kind, case.limit
    config = disabled_config(**{rule: limit})
    assert snapshot_result(build_check(report([report_node(kind, {metric: limit})]), config), 'build_check') == {"findings": []}
    actual = limit + (0.1 if metric == "instability" else 1)
    findings = snapshot_result(build_check(report([report_node(kind, {metric: actual})]), config), 'build_check')["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == rule and findings[0]["metric"] == metric
    assert findings[0]["actual"] == actual and findings[0]["limit"] == limit
    assert findings[0]["files"] == [{"path": "app.py", "line": 10}]


def test_null_disables_every_metric_check() -> None:
    measured = report([
        report_node("file", {"lineCount": 9999, "transitiveChangeImpact": 100, "instability": 1}),
        report_node("function", {"lineCount": 9999, "parameterCount": 9999, "weightedComplexity": 100, "maxDecisionDepth": 100, "nestedLoops": 100}),
    ], [{"files": ["a.py"], "exampleCycle": ["a.py", "a.py"]}])
    assert snapshot_result(build_check(measured, disabled_config()), 'build_check') == {"findings": []}
    assert snapshot_result(render_check(snapshot_result(build_check(measured, disabled_config()), 'build_check')), "render_check") == "All checks passed."


def test_missing_measurements_cannot_silently_pass_enabled_rules() -> None:
    result = snapshot_result(build_check(report([report_node("function", {"parameterCount": None})]), disabled_config(maxParameters=3)), 'build_check')
    finding = result["findings"][0]
    assert finding["actual"] is None and finding["limit"] == 3
    assert "unavailable" in finding["details"][0]
    assert "N/A" in snapshot_result(render_check(result), "render_check")


def test_isolated_instability_is_not_a_violation_and_zero_is_valid() -> None:
    nodes = [report_node("file", {"fanIn": 0, "fanOut": 0, "instability": None}),
             report_node("module", {"fanIn": 1, "fanOut": 0, "instability": 0.0})]
    assert snapshot_result(build_check(report(nodes), disabled_config(maxInstability=0)), 'build_check') == {"findings": []}


def test_dependency_limits_apply_to_files_and_modules_not_callables() -> None:
    node = report_node("function", {"instability": 1.0, "transitiveChangeImpact": 50}, "callable")
    assert snapshot_result(build_check(report([node]), disabled_config(maxChangeImpact=1, maxInstability=0.5)), 'build_check') == {"findings": []}


def test_cycle_count_maximum_and_explicit_configuration() -> None:
    cycle = {"files": ["a.py", "b.py"], "exampleCycle": ["a.py", "b.py", "a.py"]}
    measured = report(cycles=[cycle])
    finding = snapshot_result(build_check(measured, disabled_config(maxCircularImportGroups=0)), 'build_check')["findings"][0]
    assert finding["actual"] == 1 and finding["limit"] == 0
    assert finding["files"] == [{"path": "a.py"}, {"path": "b.py"}]
    assert "a.py → b.py → a.py" in snapshot_result(render_check({"findings": [finding]}), "render_check")
    assert snapshot_result(build_check(measured, disabled_config(maxCircularImportGroups=1)), 'build_check') == {"findings": []}


def test_analysis_errors_cannot_produce_a_successful_check() -> None:
    result = snapshot_result(build_check(report(diagnostics=[{"path": "bad.py", "message": "Parse failed"}]), disabled_config()), 'build_check')
    assert result["findings"][0]["rule"] == "analysis"
    assert "Parse failed" in snapshot_result(render_check(result), "render_check")


def test_real_dependency_graph_has_trackable_impact_and_instability(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(case_text('cli', 'check-real-dependency-graph-has-trackable-impact-and-instability', 'a.py'))
    (tmp_path / "b.py").write_text(case_text('cli', 'check-real-dependency-graph-has-trackable-impact-and-instability', 'b.py'))
    (tmp_path / "c.py").write_text(case_text('cli', 'check-real-dependency-graph-has-trackable-impact-and-instability', 'c.py'))
    (tmp_path / "isolated.py").write_text(case_text('cli', 'check-real-dependency-graph-has-trackable-impact-and-instability', 'isolated.py'))
    measured = snapshot_result(build_artifact_report(asdict(analyze_repository(tmp_path))), 'build_artifact_report')
    files = {node["subject"]: node["metrics"] for node in measured["nodes"] if node["kind"] == "file"}
    assert files["a.py"]["instability"] == 1.0
    assert files["b.py"]["instability"] == 0.5
    assert files["c.py"]["instability"] == 0.0
    assert files["c.py"]["transitiveChangeImpact"] == 2
    assert files["isolated.py"]["instability"] is None
    findings = snapshot_result(build_check(measured, disabled_config(maxChangeImpact=1, maxInstability=0.5)), 'build_check')["findings"]
    assert [(finding["subject"], finding["rule"]) for finding in findings] == [("a.py", "maxInstability"), ("c.py", "maxChangeImpact")]
