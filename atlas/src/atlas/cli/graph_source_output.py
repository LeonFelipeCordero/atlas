"""Numbered source excerpts with verification and navigation metadata intact."""

import json

from atlas.domain.navigation import Record


def source_text(payload: Record) -> str:
    metadata = {key: value for key, value in payload.items() if key not in {"source", "sources"}}
    sections = [json.dumps(metadata, ensure_ascii=False)]
    excerpts = payload.get("sources")
    if excerpts is None:
        excerpts = [{"stableKey": payload["filters"]["key"], **payload["source"]}]
    for excerpt in excerpts:
        details = {key: value for key, value in excerpt.items() if key != "lines"}
        lines = excerpt.get("lines", [])
        numbered = [f"{number}: {line}" for number, line in enumerate(lines, excerpt.get("startLine", 1))]
        sections.append("\n".join([f"### {excerpt.get('path', excerpt['stableKey'])}",
                                   json.dumps(details, ensure_ascii=False), *numbered]))
    return "\n\n".join(sections)
