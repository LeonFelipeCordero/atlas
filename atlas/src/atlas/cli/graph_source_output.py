"""Numbered source excerpts with verification and navigation metadata intact."""

import json

from atlas.domain.navigation import Record


def source_text(payload: Record) -> str:
    metadata = {key: value for key, value in payload.items() if key not in {"source", "sources"}}
    sections = [json.dumps(metadata, ensure_ascii=False)]
    excerpts = payload.get("sources")
    if excerpts is None:
        excerpts = [{"stableKey": payload["filters"]["key"], **payload["source"]}]
    sections.extend(excerpt_text(excerpt) for excerpt in excerpts)
    return "\n\n".join(sections)


def excerpt_text(excerpt: Record) -> str:
    details = {key: value for key, value in excerpt.items() if key != "lines"}
    numbered = [f"{number}: {line}" for number, line in enumerate(excerpt.get("lines", []), excerpt.get("startLine", 1))]
    return "\n".join([f"### {excerpt.get('path', excerpt['stableKey'])}",
                      json.dumps(details, ensure_ascii=False), *numbered])
