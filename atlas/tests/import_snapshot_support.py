"""Import-track fixture materialization and deterministic analysis seams."""

import json
from dataclasses import asdict
from pathlib import Path

from atlas.indexer import analyze_repository
from atlas.metrics.adapters.resolution import _namespace_binding
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import SourceFile, discover_files
from atlas.parsing.parser import parse_files
from tests.source_snapshot_fixture import case_text, snapshot_value

# The migration catalog records original input order, not discovery/path order.
IMPORT_CATALOG = json.loads(
    (Path(__file__).parent / "migration/imports.json").read_text()
)
IMPORT_PATHS = {
    case_id: [path.removeprefix(prefix) for path in row["fixture_paths"]
              if path.startswith(prefix)]
    for row in IMPORT_CATALOG.values()
    for case_id in row["case_ids"]
    if (prefix := f"tests/fixtures/cases/imports/{case_id}/")
    and any(path.startswith(prefix) for path in row["fixture_paths"])
}


def import_case_sources(family: str, case_id: str) -> dict[str, str]:
    """Load import fixtures in the original catalog's project input order."""
    return {path: case_text(family, case_id, path) for path in IMPORT_PATHS[case_id]}


def write_import_case(root: Path, case_id: str) -> None:
    for name, source in import_case_sources("imports", case_id).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode())


def artifact_snapshot(root: Path, case_id: str):
    write_import_case(root, case_id)
    value = asdict(analyze_repository(root))
    value["repository"]["path"] = "<case-root>"
    value["repository"]["name"] = "<case-root>"
    del value["repository"]["indexedAt"]
    for node in value["nodes"]:
        if node["stableKey"] == "repository":
            node["properties"]["absolutePath"] = "<case-root>"
        if node["stableKey"] in {"repository", "module:."}:
            node["name"] = node["qualifiedName"] = "<case-root>"
    return snapshot_value(value)


def import_snapshot(root: Path, case_id: str, spec: dict[str, str | None]):
    seam, language = spec["seam"], spec["language"]
    if seam == "artifact":
        return artifact_snapshot(root, case_id)
    assert language is not None
    if seam == "namespace-binding":
        source = next(iter(import_case_sources("imports", case_id).values()))
        return snapshot_value({"namespace_binding": _namespace_binding(source, "tools")})
    if seam == "coffee":
        repo = parse_files(discover_files(Path(__file__).parent / "fixtures/coffee/tsx"))
    else:
        repo = parse_files([
            SourceFile(path, Path("/semantic") / path, language, source.encode())
            for path, source in import_case_sources("imports", case_id).items()
        ])
    add_callable_metrics(repo)
    return snapshot_value({
        "files": [{
            "path": file.source.path,
            "parse_error": file.parse_error,
            "symbols": file.symbols,
            "calls": file.calls,
            "imports": file.imports,
        } for file in repo.files],
        "inheritances": repo.inheritances,
        "graph": resolve_connections(repo),
    })
