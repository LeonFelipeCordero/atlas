"""Configured limits evaluate the same quantitative report, never hidden policy."""

from dataclasses import asdict, dataclass
from pathlib import Path
from shutil import copytree

import pytest

from atlas.indexer import analyze_repository
from atlas.metrics.check import build_check, render_check
from atlas.metrics.config import CheckConfig
from atlas.metrics.report import build_artifact_report
from tests.coffee_fixture import FIXTURE_ROOT


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
    assert build_check(report([report_node(kind, {metric: limit})]), config) == {"findings": []}
    actual = limit + (0.1 if metric == "instability" else 1)
    findings = build_check(report([report_node(kind, {metric: actual})]), config)["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == rule and findings[0]["metric"] == metric
    assert findings[0]["actual"] == actual and findings[0]["limit"] == limit
    assert findings[0]["files"] == [{"path": "app.py", "line": 10}]


def test_null_disables_every_metric_check() -> None:
    measured = report([
        report_node("file", {"lineCount": 9999, "transitiveChangeImpact": 100, "instability": 1}),
        report_node("function", {"lineCount": 9999, "parameterCount": 9999, "weightedComplexity": 100, "maxDecisionDepth": 100, "nestedLoops": 100}),
    ], [{"files": ["a.py"], "exampleCycle": ["a.py", "a.py"]}])
    checked = build_check(measured, disabled_config())
    assert checked == {"findings": []}
    assert render_check(checked) == "All checks passed."


def test_missing_measurements_cannot_silently_pass_enabled_rules() -> None:
    result = build_check(report([report_node("function", {"parameterCount": None})]), disabled_config(maxParameters=3))
    finding = result["findings"][0]
    assert finding["actual"] is None and finding["limit"] == 3
    assert "unavailable" in finding["details"][0]
    assert "N/A" in render_check(result)


def test_isolated_instability_is_not_a_violation_and_zero_is_valid() -> None:
    nodes = [report_node("file", {"fanIn": 0, "fanOut": 0, "instability": None}),
             report_node("module", {"fanIn": 1, "fanOut": 0, "instability": 0.0})]
    assert build_check(report(nodes), disabled_config(maxInstability=0)) == {"findings": []}


def test_dependency_limits_apply_to_files_and_modules_not_callables() -> None:
    node = report_node("function", {"instability": 1.0, "transitiveChangeImpact": 50}, "callable")
    assert build_check(report([node]), disabled_config(maxChangeImpact=1, maxInstability=0.5)) == {"findings": []}


def test_cycle_count_maximum_and_explicit_configuration() -> None:
    cycle = {"files": ["a.py", "b.py"], "exampleCycle": ["a.py", "b.py", "a.py"]}
    measured = report(cycles=[cycle])
    finding = build_check(measured, disabled_config(maxCircularImportGroups=0))["findings"][0]
    assert finding["actual"] == 1 and finding["limit"] == 0
    assert finding["files"] == [{"path": "a.py"}, {"path": "b.py"}]
    assert "a.py → b.py → a.py" in render_check({"findings": [finding]})
    assert build_check(measured, disabled_config(maxCircularImportGroups=1)) == {"findings": []}


def test_analysis_errors_cannot_produce_a_successful_check() -> None:
    result = build_check(report(diagnostics=[{"path": "bad.py", "message": "Parse failed"}]), disabled_config())
    assert result["findings"][0]["rule"] == "analysis"
    assert "Parse failed" in render_check(result)


def test_real_dependency_graph_has_trackable_impact_and_instability(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    measured = build_artifact_report(asdict(analyze_repository(tmp_path)))
    files = {node["subject"]: node["metrics"] for node in measured["nodes"] if node["kind"] == "file"}
    assert files["src/coffee/orders/service.py"]["instability"] == 1.0
    assert files["src/coffee/inventory/stock.py"]["instability"] == 0.5
    assert files["src/coffee/orders/models.py"]["instability"] == 0.0
    assert files["src/coffee/orders/models.py"]["transitiveChangeImpact"] == 6
    assert files["src/coffee/reporting/report.py"]["instability"] == 0.25
    findings = build_check(measured, disabled_config(maxChangeImpact=1, maxInstability=0.5))["findings"]
    assert {finding["rule"] for finding in findings} == {"maxChangeImpact", "maxInstability"}
    assert {
        ("src/coffee/orders/models.py", "maxChangeImpact"),
        ("src/coffee/orders/service.py", "maxInstability"),
    } <= {(finding["subject"], finding["rule"]) for finding in findings}
