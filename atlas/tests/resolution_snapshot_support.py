"""Named complete inputs for resolution regressions and their record snapshots."""

import json
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from atlas.domain.models import ParsedRepository, SourceFile
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.parser import parse_files
from tests.source_snapshot_fixture import (
    case_bytes,
    case_sources,
    case_text,
    snapshot_value,
)
from tests.resolution_adapter_snapshot_records import adapter_records

MANIFEST = json.loads(
    (Path(__file__).parent / "migration" / "resolution.json").read_text()
)


def fixture_id(site: str, **selectors: Any) -> str:
    route = MANIFEST["routes"][site]
    values = snapshot_value([selectors[name] for name in route["selectors"]])
    return next(case["id"] for case in route["cases"] if case["values"] == values)


def fixture_sources(site: str, **selectors: Any) -> dict[str, str]:
    return ordered_sources(fixture_id(site, **selectors))


def ordered_sources(case_id: str) -> dict[str, str]:
    sources = case_sources("resolution", case_id)
    return {path: sources[path] for path in MANIFEST["cases"][case_id]["paths"]}


def fixture_bytes(site: str, **selectors: Any) -> bytes:
    case_id = fixture_id(site, **selectors)
    return case_bytes("resolution", case_id, MANIFEST["cases"][case_id]["paths"][0])


def fixture_text(site: str, path: str, **selectors: Any) -> str:
    return case_text("resolution", fixture_id(site, **selectors), path)


def case_repository(case_id: str) -> ParsedRepository:
    language = MANIFEST["cases"][case_id]["language"]
    return parse_files(
        [
            SourceFile(path, Path("/resolution") / path, language, source.encode())
            for path, source in ordered_sources(case_id).items()
        ]
    )


def syntax_record(node: Node) -> dict[str, Any]:
    """Lossless syntax seam for adapter probes, including unnamed punctuation."""
    return {
        "type": node.type,
        "named": node.is_named,
        "error": node.has_error,
        "missing": node.is_missing,
        "start_byte": node.start_byte,
        "end_byte": node.end_byte,
        "start_point": list(node.start_point),
        "end_point": list(node.end_point),
        "text": node.text,
        "children": [syntax_record(child) for child in node.children],
    }


def case_records(case_id: str) -> dict[str, Any]:
    repo = case_repository(case_id)
    files = [
        {
            "path": file.source.path,
            "language": file.source.language,
            "content_hash": file.content_hash,
            "parse_error": file.parse_error,
            "symbols": file.symbols,
            "imports": file.imports,
            "calls": file.calls,
            "inheritances": file.inheritances,
        }
        for file in repo.files
    ]
    records: dict[str, Any] = {"files": files, "resolved": resolve_connections(repo)}
    adapters = adapter_records(case_id, repo)
    if adapters:
        records["adapter"] = adapters
    case = MANIFEST["cases"][case_id]
    if case["seam"] == "parser":
        source = case_bytes("resolution", case_id, case["paths"][0])
        records["syntax"] = syntax_record(
            get_parser(case["language"]).parse(source).root_node
        )
    return records
