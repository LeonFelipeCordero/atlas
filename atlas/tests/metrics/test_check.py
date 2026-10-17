"""Enabled limits use strict excess, kind/level routing, and explicit missing data."""

from typing import Any

import pytest

from atlas.metrics.check import build_check, render_check
from atlas.metrics.config import CheckConfig


@pytest.fixture
def disabled() -> CheckConfig:
    return CheckConfig.model_validate(dict.fromkeys(CheckConfig.model_fields))


def report(*nodes: dict[str, Any], **overrides) -> dict[str, Any]:
    return {"nodes": list(nodes), "summary": {"circularImportGroups": 0},
            "circularImports": [], "diagnostics": [], **overrides}


def node(kind: str = "function", level: str = "callable", **metrics) -> dict[str, Any]:
    return {"kind": kind, "level": level, "subject": "brew", "path": "a.py",
            "line": 3, "metrics": metrics}


@pytest.mark.parametrize("case", [
    ("maxFileLines", "lineCount", "Lines", "file", "file"),
    ("maxFunctionLines", "lineCount", "Lines", "function", "callable"),
    ("maxParameters", "parameterCount", "Parameters", "method", "callable"),
    ("maxWeightedComplexity", "weightedComplexity", "Weighted complexity", "function", "callable"),
    ("maxDecisionDepth", "maxDecisionDepth", "Decision depth", "method", "callable"),
    ("maxNestedLoops", "nestedLoops", "Nested loops", "function", "callable"),
    ("maxChangeImpact", "transitiveChangeImpact", "Change impact", "directory", "module"),
    ("maxInstability", "instability", "Internal instability", "file", "file"),
])
@pytest.mark.parametrize("offset", [None, -1, 0, 1])
def test_enabled_limit_exact_boundary_and_missing_measurement(disabled, case, offset) -> None:
    rule, metric, label, kind, level = case
    maximum = 0.5 if metric == "instability" else 1
    actual = None if offset is None else maximum + offset * maximum
    config = CheckConfig.model_validate({**disabled.model_dump(), rule: maximum})
    measured = node(kind, level, **({metric: actual} if actual is not None else {}))

    result = build_check(report(measured), config)

    expected = [] if actual is not None and actual <= maximum else [{
        "rule": rule, "metric": metric, "subject": "brew",
        "files": [{"path": "a.py", "line": 3}], "actual": actual, "limit": maximum,
        "details": [f"{label} is unavailable; cannot evaluate maximum {maximum}."
                    if actual is None else f"{label} is {actual} (maximum: {maximum})."],
    }]
    assert result == {"findings": expected}


@pytest.mark.parametrize(("kind", "level"), [("class", "type"), ("constructor", "callable"),
                                                  ("function", "symbol")])
def test_disabled_and_inapplicable_rules_do_not_produce_findings(disabled, kind, level) -> None:
    config = disabled.model_copy(update={"maxFileLines": 0, "maxChangeImpact": 0, "maxInstability": 0.0})

    result = build_check(report(node(kind, level)), config)

    assert result == {"findings": []}


@pytest.mark.parametrize(("metrics", "expected_count"), [
    ({"fanIn": 0, "fanOut": 0}, 0), ({"fanIn": 0, "fanOut": 1}, 1),
    ({"fanIn": 1, "fanOut": 0}, 1), ({}, 1),
])
def test_only_known_isolated_nodes_skip_unavailable_instability(disabled, metrics, expected_count) -> None:
    config = disabled.model_copy(update={"maxInstability": 0.5})

    result = build_check(report(node("file", "file", **metrics)), config)

    assert [finding["actual"] for finding in result["findings"]] == [None] * expected_count


@pytest.mark.parametrize("maximum", [None, 2, 3])
def test_cycles_at_or_below_limit_or_disabled_pass(disabled, maximum) -> None:
    config = disabled.model_copy(update={"maxCircularImportGroups": maximum})

    result = build_check(report(summary={"circularImportGroups": 2}), config)

    assert result == {"findings": []}


def test_findings_keep_node_then_cycle_then_diagnostic_order(disabled) -> None:
    config = disabled.model_copy(update={"maxParameters": 0, "maxCircularImportGroups": 0})
    source_report = report(node(parameterCount=2), circularImports=[
        {"files": ["z.py", "a.py"], "exampleCycle": ["z.py", "a.py", "z.py"]},
        {"files": ["a.py", "b.py"], "exampleCycle": ["a.py", "b.py", "a.py"]},
    ], summary={"circularImportGroups": 2}, diagnostics=[{"path": "bad.py", "message": "bad syntax"}])

    result = build_check(source_report, config)

    assert result == {"findings": [
        {"rule": "maxParameters", "metric": "parameterCount", "subject": "brew",
         "files": [{"path": "a.py", "line": 3}], "actual": 2, "limit": 0,
         "details": ["Parameters is 2 (maximum: 0)."]},
        {"rule": "maxCircularImportGroups", "metric": "circularImportGroups", "subject": "Circular imports",
         "actual": 2, "limit": 0, "files": [{"path": "a.py"}, {"path": "b.py"}, {"path": "z.py"}],
         "details": ["Circular import groups: 2 (maximum: 0).",
                     "Example cycle: z.py → a.py → z.py", "Example cycle: a.py → b.py → a.py"]},
        {"rule": "analysis", "metric": "parseError", "subject": "Analysis incomplete",
         "files": [{"path": "bad.py"}], "actual": None, "limit": None, "details": ["bad syntax"]},
    ]}


def test_diagnostics_fail_even_when_all_limits_are_disabled(disabled) -> None:
    result = build_check(report(diagnostics=[{"message": "unreadable"}]), disabled)

    assert result == {"findings": [{
        "rule": "analysis", "metric": "parseError", "subject": "Analysis incomplete",
        "files": [{"path": None}], "actual": None, "limit": None, "details": ["unreadable"],
    }]}


def test_render_pass() -> None:
    assert render_check({"findings": []}) == "All checks passed."


def test_render_multiple_findings_with_missing_values_and_literal_names() -> None:
    finding = {"rule": "maxInstability", "subject": "a|b", "actual": 0.75, "limit": 0.5,
               "files": [{"path": "a.py", "line": 2}], "details": ["Too unstable."]}
    unavailable = {"rule": "analysis", "subject": "bad", "actual": None, "limit": None,
                   "files": [{}], "details": ["No source."]}

    result = render_check({"findings": [finding, unavailable]})

    assert result == (
        "## maxInstability: `a\\|b`\n\nMeasured: 0.75; maximum: 0.50.\n\n"
        "- `a.py:2`\n\n- Too unstable.\n\n"
        "## analysis: `bad`\n\nMeasured: N/A; maximum: N/A.\n\n"
        "- `Unknown file`\n\n- No source."
    )
