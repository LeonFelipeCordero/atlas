"""Readable quantitative Markdown and shared literal source formatting."""

from collections import Counter
from typing import Any

METRIC_LABELS = {
    "lineCount": "Lines", "parameterCount": "Parameters",
    "cyclomaticComplexity": "Cyclomatic complexity", "weightedComplexity": "Weighted complexity",
    "nestedDecisionPenalty": "Nested decision penalty", "nestedLoops": "Nested loops",
    "maxDecisionDepth": "Decision depth", "fanIn": "Fan-in", "fanOut": "Fan-out",
    "transitiveChangeImpact": "Change impact", "instability": "Internal instability",
    "functionCount": "Functions/methods", "measuredFunctionCount": "Measured functions/methods",
    "weightedComplexitySum": "Weighted complexity sum",
}


def code(value: str) -> str:
    """Keep source names literal, including Markdown delimiters and table pipes."""
    value = value.replace("\n", " ").replace("\r", " ").replace("|", "\\|")
    fence = "`"
    while fence in value:
        fence += "`"
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{padding}{value}{padding}{fence}"


def location(node: dict[str, Any]) -> str:
    path = node.get("path") or "Unknown file"
    return f"{path}:{node['line']}" if node.get("line") is not None else path


def value_text(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _table_row(node: dict[str, Any], names: tuple[str, ...]) -> str:
    cells = (code(node["subject"]), code(location(node)), *(value_text(node["metrics"].get(name)) for name in names))
    return "| " + " | ".join(cells) + " |"


def _table(title: str, nodes: list[dict[str, Any]], names: tuple[str, ...]) -> str:
    labels = ("Item", "Location", *(METRIC_LABELS[name] for name in names))
    rows = [f"## {title}", "", "| " + " | ".join(labels) + " |", "| " + " | ".join("---" for _ in labels) + " |"]
    rows.extend(_table_row(node, names) for node in nodes)
    return "\n".join(rows)


def _cycle_section(index: int, group: dict[str, Any]) -> list[str]:
    return [
        f"### Group {index}", "",
        f"Files: {group['groupSize']}. Internal dependencies: {group['internalDependencyCount']}.",
        *[f"- {code(path)}" for path in group["files"]], "",
        "Example cycle: " + " → ".join(code(path) for path in group["exampleCycle"]), "",
    ]


def _cycles(groups: list[dict[str, Any]]) -> str:
    rows = ["## Circular imports", ""]
    for index, group in enumerate(groups, 1):
        rows.extend(_cycle_section(index, group))
    return "\n".join(rows).rstrip()


def _size_tables(nodes: list[dict[str, Any]]) -> list[str]:
    parts = []
    files = [node for node in nodes if node["kind"] == "file"]
    callables = [node for node in nodes if node["kind"] in {"function", "method"}]
    if files:
        parts.append(_table("Files", files, ("lineCount", "functionCount", "measuredFunctionCount", "weightedComplexitySum")))
    if callables:
        parts.append(_table("Callables", callables, (
            "lineCount", "parameterCount", "cyclomaticComplexity", "weightedComplexity",
            "nestedDecisionPenalty", "nestedLoops", "maxDecisionDepth",
        )))
    return parts


def _dependencies(nodes: list[dict[str, Any]]) -> list[str]:
    if not nodes:
        return []
    return [
        _table("Dependencies", [node for node in nodes if "fanIn" in node["metrics"]], (
            "fanIn", "fanOut", "transitiveChangeImpact", "instability",
        )),
        "Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.",
    ]


def _mutation_candidate_row(candidate: dict[str, Any]) -> str:
    span = candidate["span"]
    location = f"{candidate['path']}:{span['startLine']}:{span['startColumn']}"
    cells = [location, candidate["kind"], candidate.get("operator") or "—", candidate["originalText"]]
    return "| " + " | ".join(code(cell) for cell in cells) + " |"


def _mutation_diagnostics(diagnostics: list[dict[str, Any]]) -> list[str]:
    if not diagnostics:
        return []
    return ["", "### Candidate analysis limitations", "", *(
        f"- {code(item['path'])} [{code(item['code'])}]: {item['message']}"
        for item in diagnostics
    )]


def _mutation_candidates(report: dict[str, Any]) -> str:
    candidates = report.get("mutationCandidates", [])
    diagnostics = report.get("mutationCandidateDiagnostics", [])
    if not candidates and not diagnostics:
        return ""
    counts = Counter(candidate["kind"] for candidate in candidates)
    rows = [
        "## Mutation candidates", "",
        "Identified source sites only; no mutations generated or tests executed.", "",
        ", ".join(f"{kind}: {count}" for kind, count in sorted(counts.items())) or "No candidates.",
    ]
    if candidates:
        rows.extend(["", "| Location (byte columns) | Kind | Operator | Original source |",
                     "| --- | --- | --- | --- |"])
        rows.extend(_mutation_candidate_row(candidate) for candidate in candidates)
    rows.extend(_mutation_diagnostics(diagnostics))
    return "\n".join(rows)


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    parts = ["# Metrics", "\n".join(f"- {name}: {value}" for name, value in summary.items())]
    parts.extend(_size_tables(report["nodes"]))
    parts.extend(_dependencies(report["nodes"]))
    if report["circularImports"]:
        parts.append(_cycles(report["circularImports"]))
    if report["diagnostics"]:
        parts.append("## Analysis diagnostics\n\n" + "\n".join(
            f"- {code(diagnostic.get('path') or 'Unknown file')}: {diagnostic['message']}"
            for diagnostic in report["diagnostics"]
        ))
    candidates = _mutation_candidates(report)
    if candidates:
        parts.append(candidates)
    return "\n\n".join(parts)
