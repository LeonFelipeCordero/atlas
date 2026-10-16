"""Evaluate only enabled project limits against quantitative measurements."""

from dataclasses import dataclass
from typing import Any

from .config import CheckConfig
from .report_markdown import METRIC_LABELS, code, location, value_text

RULES = (
    ("maxFileLines", "lineCount", {"file"}),
    ("maxFunctionLines", "lineCount", {"function", "method"}),
    ("maxParameters", "parameterCount", {"function", "method"}),
    ("maxWeightedComplexity", "weightedComplexity", {"function", "method"}),
    ("maxDecisionDepth", "maxDecisionDepth", {"function", "method"}),
    ("maxNestedLoops", "nestedLoops", {"function", "method"}),
)
DEPENDENCY_RULES = (
    ("maxChangeImpact", "transitiveChangeImpact"),
    ("maxInstability", "instability"),
)


@dataclass(frozen=True)
class _MetricLimit:
    rule: str
    metric: str
    maximum: int | float


def _finding(node, limit: _MetricLimit, actual):
    label = METRIC_LABELS[limit.metric]
    details = (
        f"{label} is unavailable; cannot evaluate maximum {limit.maximum}."
        if actual is None else f"{label} is {actual} (maximum: {limit.maximum})."
    )
    return {
        "rule": limit.rule, "metric": limit.metric, "subject": node["subject"],
        "files": [{"path": node.get("path"), "line": node.get("line")}],
        "actual": actual, "limit": limit.maximum, "details": [details],
    }


def _metric_finding(node, limit: _MetricLimit):
    actual = node["metrics"].get(limit.metric)
    if actual is None or actual > limit.maximum:
        return _finding(node, limit, actual)
    return None


def _enabled_limits(node, config: CheckConfig):
    rules = [(rule, metric) for rule, metric, kinds in RULES if node["kind"] in kinds]
    if node["level"] in {"module", "file"}:
        rules.extend(DEPENDENCY_RULES)
    for rule, metric in rules:
        maximum = getattr(config, rule)
        if maximum is not None:
            yield _MetricLimit(rule, metric, maximum)


def _isolated(node) -> bool:
    return node["metrics"].get("fanIn") == node["metrics"].get("fanOut") == 0


def _node_findings(node, config: CheckConfig):
    findings = []
    for limit in _enabled_limits(node, config):
        # Zero connections make instability mathematically undefined, not missing.
        if limit.metric == "instability" and _isolated(node):
            continue
        finding = _metric_finding(node, limit)
        if finding is not None:
            findings.append(finding)
    return findings


def _cycle_files(groups):
    paths = set()
    for group in groups:
        paths.update(group["files"])
    return [{"path": path} for path in sorted(paths)]


def _cycle_finding(report, limit):
    count = report["summary"]["circularImportGroups"]
    if limit is None or count <= limit:
        return []
    return [{
        "rule": "maxCircularImportGroups", "metric": "circularImportGroups",
        "subject": "Circular imports", "actual": count, "limit": limit,
        "files": _cycle_files(report["circularImports"]),
        "details": [
            f"Circular import groups: {count} (maximum: {limit}).",
            *["Example cycle: " + " → ".join(group["exampleCycle"]) for group in report["circularImports"]],
        ],
    }]


def build_check(report: dict[str, Any], config: CheckConfig) -> dict[str, Any]:
    """Return findings for exceeded limits, missing enabled metrics, and diagnostics.

    Consume a metrics report without modifying it. Null limits are disabled;
    isolated nodes skip undefined instability. An empty findings list means pass.
    """
    findings = [finding for node in report["nodes"] for finding in _node_findings(node, config)]
    findings.extend(_cycle_finding(report, config.maxCircularImportGroups))
    findings.extend({
        "rule": "analysis", "metric": "parseError", "subject": "Analysis incomplete",
        "files": [{"path": diagnostic.get("path")}],
        "actual": None, "limit": None, "details": [diagnostic["message"]],
    } for diagnostic in report["diagnostics"])
    return {"findings": findings}


def _finding_section(finding) -> str:
    files = [f"- {code(location(file))}" for file in finding["files"]]
    return "\n".join([
        f"## {finding['rule']}: {code(finding['subject'])}", "",
        f"Measured: {value_text(finding['actual'])}; maximum: {value_text(finding['limit'])}.",
        "", *files, "", *[f"- {detail}" for detail in finding["details"]],
    ])


def render_check(check: dict[str, Any]) -> str:
    """Format findings as Markdown, or return 'All checks passed.' when empty."""
    if not check["findings"]:
        return "All checks passed."
    return "\n\n".join(_finding_section(finding) for finding in check["findings"])
