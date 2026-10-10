"""Evaluate only enabled project limits against quantitative measurements."""

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


def _finding(node, rule: str, metric: str, actual, limit, details: str):
    return {
        "rule": rule, "metric": metric, "subject": node["subject"],
        "files": [{"path": node.get("path"), "line": node.get("line")}],
        "actual": actual, "limit": limit, "details": [details],
    }


def _metric_finding(node, rule: str, metric: str, limit):
    actual = node["metrics"].get(metric)
    label = METRIC_LABELS[metric]
    if actual is None:
        return _finding(node, rule, metric, None, limit, f"{label} is unavailable; cannot evaluate maximum {limit}.")
    if actual > limit:
        return _finding(node, rule, metric, actual, limit, f"{label} is {actual} (maximum: {limit}).")
    return None


def _node_findings(node, config: CheckConfig):
    rules = [(rule, metric) for rule, metric, kinds in RULES if node["kind"] in kinds]
    if node["level"] in {"module", "file"}:
        rules.extend(DEPENDENCY_RULES)
    findings = []
    for rule, metric in rules:
        limit = getattr(config, rule)
        if limit is None:
            continue
        # Zero connections make instability mathematically undefined, not missing.
        if metric == "instability" and node["metrics"].get("fanIn") == node["metrics"].get("fanOut") == 0:
            continue
        finding = _metric_finding(node, rule, metric, limit)
        if finding is not None:
            findings.append(finding)
    return findings


def _cycle_finding(report, limit):
    count = report["summary"]["circularImportGroups"]
    if limit is None or count <= limit:
        return []
    return [{
        "rule": "maxCircularImportGroups", "metric": "circularImportGroups",
        "subject": "Circular imports", "actual": count, "limit": limit,
        "files": [{"path": path} for path in sorted({
            path for group in report["circularImports"] for path in group["files"]
        })],
        "details": [
            f"Circular import groups: {count} (maximum: {limit}).",
            *["Example cycle: " + " → ".join(group["exampleCycle"]) for group in report["circularImports"]],
        ],
    }]


def build_check(report: dict[str, Any], config: CheckConfig) -> dict[str, Any]:
    """Null limits are disabled; incomplete enabled measurements cannot pass."""
    findings = [finding for node in report["nodes"] for finding in _node_findings(node, config)]
    findings.extend(_cycle_finding(report, config.maxCircularImportGroups))
    findings.extend({
        "rule": "analysis", "metric": "parseError", "subject": "Analysis incomplete",
        "files": [{"path": diagnostic.get("path")}],
        "actual": None, "limit": None, "details": [diagnostic["message"]],
    } for diagnostic in report["diagnostics"])
    return {"findings": findings}


def render_check(check: dict[str, Any]) -> str:
    if not check["findings"]:
        return "All checks passed."
    sections = []
    for finding in check["findings"]:
        files = [f"- {code(location(file))}" for file in finding["files"]]
        sections.append("\n".join([
            f"## {finding['rule']}: {code(finding['subject'])}", "",
            f"Measured: {value_text(finding['actual'])}; maximum: {value_text(finding['limit'])}.",
            "", *files, "", *[f"- {detail}" for detail in finding["details"]],
        ]))
    return "\n\n".join(sections)
