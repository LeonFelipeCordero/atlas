"""Snapshot named project overlays using their actual discovered grammars."""

import json
from dataclasses import asdict, replace
from pathlib import Path

from tree_sitter_language_pack import ProcessConfig, get_parser, process

from atlas.metrics.artifact import build_artifact
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import LANGUAGES, SNAPSHOT_ROOT, coffee_sources
from tests.coffee_pipeline import grammar_variant, source_structures
from tests.project_snapshot_support import parsed_value, structure_value
from tests.source_snapshot_fixture import snapshot_value

VARIANT_ROOT = Path(__file__).parent / "fixtures" / "variants"
VARIANT_SNAPSHOT_ROOT = SNAPSHOT_ROOT / "variants"


def variant_groups():
    return sorted(path.name for path in VARIANT_ROOT.iterdir() if path.is_dir())


def variant_snapshot(group):
    root = VARIANT_ROOT / group
    scenarios = {path.name: scenario_snapshot(path) for path in sorted(root.iterdir()) if path.is_dir()}
    files = {path.name: path.read_bytes() for path in sorted(root.iterdir()) if path.is_file()}
    if files:
        sources = [source for source in discover_files(root) if source.path in files]
        scenarios["file-boundaries"] = snapshot_records(root / "file-boundaries", sources, files)
    return scenarios


def scenario_snapshot(root):
    inputs = {path.relative_to(root).as_posix(): path.read_bytes()
              for path in sorted(root.rglob("*")) if path.is_file()}
    records = snapshot_records(root, scenario_sources(root), inputs)
    if root.parent.name == "c":  # Native legacy includes, not production importer support.
        records["native_only"] = {path: legacy_c_snapshot(content) for path, content in inputs.items()}
    return records


def legacy_c_snapshot(content):
    root = get_parser("c").parse(content).root_node
    native = process(content.decode(), ProcessConfig(language="c")).structure
    return {"language": "c", "syntax": str(root), "has_error": root.has_error,
            "native": structure_value(native)}


def snapshot_records(root, sources, inputs):
    repository = parse_files(sources)
    extraction = snapshot_value([parsed_value(file) for file in repository.files])
    add_callable_metrics(repository)
    resolved = resolve_connections(repository)
    artifact = asdict(build_artifact(root, repository, resolved))
    del artifact["repository"]["indexedAt"]
    stable_root = f"/samples/variants/{root.parent.name}/{root.name}"
    artifact["repository"]["path"] = stable_root
    artifact["nodes"][0]["properties"]["absolutePath"] = stable_root
    return snapshot_value({
        "inputs": inputs,
        "extraction": extraction,
        "structures": {source.path: source_structures(source) for source in sources},
        "grammar_variants": {source.path: {"tsx": grammar_variant(source, sources, "tsx")}
                             for source in sources if source.path in inputs and source.path.endswith(".jsx")},
        "analysis": {"symbols": repository.symbols, "resolved": resolved},
        "graph": artifact,
    })


def scenario_sources(root):
    # Language variants are overlays of the complete application, not fragments.
    base = coffee_sources(root.parent.name) if root.parent.name in LANGUAGES else []
    sources = {source.path: replace(source, absolute_path=root / source.path) for source in base}
    sources.update({source.path: source for source in discover_files(root)})
    return list(sources.values())


def write_variants():
    VARIANT_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    for group in variant_groups():
        (VARIANT_SNAPSHOT_ROOT / f"{group}.json").write_text(
            json.dumps(variant_snapshot(group), ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
