"""Collect every analysis seam from the same complete, realistic sample project."""

import json
from dataclasses import replace
from functools import cache
from itertools import product

from click.testing import CliRunner
from tree_sitter_language_pack import ProcessConfig, get_parser, process

from atlas.cli import main
from atlas.metrics.artifact import build_artifact
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import detect_language
from atlas.parsing.parser import parse_files
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import FIXTURE_ROOT, SNAPSHOT_ROOT, coffee_snapshot, coffee_sources
from tests.project_snapshot_support import parsed_value, structure_value
from tests.source_snapshot_fixture import snapshot_value

PIPELINE_ROOT = SNAPSHOT_ROOT / "coffee"
SEAMS = ("extraction", "analysis", "graph", "cli")
GRAMMAR_VARIANTS = {
    "typescript": {"ordering/Order.ts": ("tsx",), "ordering/Scheduling.ts": ("tsx",)},
    "javascript": {"ordering/Dispatch.js": ("typescript", "tsx"),
                   "ordering/DispatchView.jsx": ("tsx",)},
}


@cache
def project_analysis(language):
    sources = coffee_sources(language)
    repository = parse_files(sources)
    # Freeze before enrichment: metric enrichment mutates the Symbol objects.
    extraction = snapshot_value([parsed_value(file) for file in repository.files])
    structures = {source.path: source_structures(source) for source in sources}
    add_callable_metrics(repository)
    resolved = resolve_connections(repository)
    analysis = snapshot_value({"symbols": repository.symbols, "resolved": resolved})
    artifact = build_artifact(FIXTURE_ROOT / language, repository, resolved)
    return {
        "extraction": {"files": extraction, "structures": structures,
                       "excluded_sources": excluded_sources(language),
                       "grammar_variants": shared_grammar_variants(language, sources)},
        "analysis": analysis,
        "graph": coffee_snapshot(artifact),
    }


def excluded_sources(language):
    root = FIXTURE_ROOT / language
    records = {}
    for path in sorted((root / "edge_cases").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or detect_language(path) is not None:
            continue
        content = path.read_bytes()
        record = {"bytes": snapshot_value(content)}
        if path.suffix == ".h":
            syntax = get_parser("c").parse(content).root_node
            native = process(content.decode(), ProcessConfig(language="c")).structure
            record["native_only"] = {"language": "c", "syntax": str(syntax),
                                     "has_error": syntax.has_error, "native": structure_value(native)}
        records[path.relative_to(root).as_posix()] = record
    return records


def shared_grammar_variants(language, sources):
    variants = dict(GRAMMAR_VARIANTS.get(language, {}))
    variants.update({source.path: ("tsx",) for source in sources if source.path.endswith(".jsx")})
    by_path = {source.path: source for source in sources}
    return {path: {grammar: grammar_variant(by_path[path], sources, grammar)
                   for grammar in grammars} for path, grammars in variants.items()}


def grammar_variant(source, sources, grammar):
    variant = replace(source, language=grammar)
    repository = parse_files([variant if item.path == source.path else item for item in sources])
    file = next(file for file in repository.files if file.source.path == source.path)
    parser = snapshot_value(parsed_value(file))
    add_callable_metrics(repository)
    return {
        "parser": parser,
        "structures": source_structures(variant),
        "analysis": snapshot_value({"symbols": file.symbols,
                                    **grammar_resolution(source.path, resolve_connections(repository))}),
    }


def grammar_resolution(path, resolved):
    connections = [edge for edge in resolved.connections if edge.path == path]
    targets = {edge.target_key for edge in connections}
    return {"connections": connections,
            "external_nodes": [node for node in resolved.external_nodes if node.key in targets]}


def source_structures(source):
    native = process(
        source.source.decode("utf-8", errors="replace"), ProcessConfig(language=source.language)
    ).structure
    syntax = ParsedSyntax(source)
    before = structure_value(native)
    result = {
        "native": before,
        "tags_only": structure_value(extract_structure(syntax, [])),
        "merged": structure_value(extract_structure(syntax, native)),
    }
    assert structure_value(native) == before, source.path
    return result


def project_cli(language):
    outputs = {}
    for command, format in product(("report", "check"), ("json", "markdown")):
        result = CliRunner().invoke(main, [
            command, "--folder", str(FIXTURE_ROOT / language), "--format", format,
        ])
        assert result.exit_code in (0, 1), result.output
        assert result.exception is None or isinstance(result.exception, SystemExit), result.output
        outputs[f"{command}-{format}"] = {
            "exit_code": result.exit_code,
            "output": json.loads(result.output) if format == "json" else result.output,
            "stderr": result.stderr,
        }
    return outputs


@cache
def coffee_pipeline(language):
    return {**project_analysis(language), "cli": project_cli(language)}


def write_pipeline(language):
    bundle = coffee_pipeline(language)
    for seam in SEAMS:
        path = PIPELINE_ROOT / language / f"{seam}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(bundle[seam], ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8",
        )
