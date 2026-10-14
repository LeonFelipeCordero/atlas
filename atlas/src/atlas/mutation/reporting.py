"""Human-readable mutation inventory and agent-reported experiment evidence."""

from typing import Any


def _text(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _trial_lines(trial: dict[str, Any]) -> list[str]:
    result = trial["result"]
    lines = [
        f"#### Trial {trial['trial_id']} — {result['outcome']} (agent-reported)", "",
        f"Hypothesis: {_text(result['hypothesis'])}", "",
        f"Explanation: {_text(result['explanation'])}", "",
    ]
    for label in ("baseline", "mutant"):
        evidence = result.get(label)
        if evidence:
            lines.append(f"{label.title()}: `{_text(evidence['command'])}`; exit {evidence['exit_code']}; {evidence['duration_seconds']}s; log: {_text(evidence['log_reference'])}")
    lines.extend(["", f"Source identities: {_text(result['source_identity'])}", "", "Patch:", ""])
    # Use an indented block: an agent's patch cannot terminate the fence.
    lines.extend("    " + line for line in result["patch"].splitlines())
    return [*lines, ""]


def render_mutation_markdown(report: dict[str, Any]) -> str:
    scope = report["scope"]
    lines = [
        "# Mutation experiment ledger", "",
        f"Session: `{report['session_id']}`", "",
        f"Root: {_text(report['root'])}", "",
        f"Scope: {scope['mode']}; folders: {', '.join(map(_text, scope['folders']))}", "",
        f"Base: {_text(scope.get('requested_base') or 'none')} → {_text(scope.get('resolved_base') or 'none')}", "",
        "Results are agent-reported, not independently verified. Survivors are candidate testing gaps, not proof of missing required behavior.", "",
        "## Agent-reported trial counts", "",
        "; ".join(f"{outcome}: {count}" for outcome, count in report["outcome_counts"].items()), "",
        f"Unexplored sites (no recorded trial): {len(report['unexplored_sites'])}", "",
        "## Source snapshot status", "",
        "| Path | Current source | Snapshot SHA-256 |", "| --- | --- | --- |",
    ]
    lines.extend(f"| {_text(source['path'])} | {source['current_source_status']} | {source['original_file_hash']} |" for source in report["sources"])
    lines.extend(["", "## Opportunities", ""])
    for site in report["sites"]:
        lines.extend(_site_lines(site, report))
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {_text(item['path'])}: {item['code']} — {_text(item['message'])}" for item in report["limitations"])
    if not report["limitations"]:
        lines.append("None reported; this is not a claim of complete mutation coverage.")
    return "\n".join(lines) + "\n"


def _site_lines(site: dict[str, Any], report: dict[str, Any]) -> list[str]:
    span = site["span"]
    lines = [
        f"### `{site['site_id']}`", "",
        f"{_text(site['path'])}:{span['start_line']}:{span['start_column']} — {site['language']} / {site['kind']}", "",
        f"Expression: {_text(site['expression'])}", "",
        f"Callable: {_text(site['callable'] or '(module)')}; selection: {site['diff_relationship']}", "",
        f"Bytes: [{span['start_byte']}, {span['end_byte']}); coordinates are one-based lines and byte columns.", "",
        "Context:", "",
        *("    " + line for line in site["context"].splitlines()), "",
    ]
    trials = [trial for trial in report["trials"] if trial["site_id"] == site["site_id"]]
    if not trials:
        lines.extend(["Unexplored: no recorded trial.", ""])
    for trial in trials:
        lines.extend(_trial_lines(trial))
    return lines
