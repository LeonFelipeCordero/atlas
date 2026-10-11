"""Collect every analysis seam from the same complete, realistic sample project."""

import json
from dataclasses import replace
from functools import cache
from itertools import product
from pathlib import Path

from click.testing import CliRunner
from tree_sitter_language_pack import ProcessConfig, process

from atlas.cli import main
from atlas.metrics.artifact import build_artifact
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.parser import parse_file, parse_files
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import FIXTURE_ROOT, SNAPSHOT_ROOT, coffee_snapshot, coffee_sources
from tests.parsing_snapshot_support import parsed_value, structure_value
from tests.source_snapshot_fixture import snapshot_value

PIPELINE_ROOT = SNAPSHOT_ROOT / "coffee"
SEAMS = ("extraction", "analysis", "cli")


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
                       "grammar_variants": shared_grammar_variants(language, sources)},
        "analysis": analysis,
        "graph": coffee_snapshot(artifact),
    }


def shared_grammar_variants(language, sources):
    if language != "typescript":
        return {}
    source = next(source for source in sources if source.path == "ordering/Order.ts")
    variant = replace(source, language="tsx")
    return {source.path: {"tsx": {
        "parser": snapshot_value(parsed_value(parse_file(variant))),
        "structures": source_structures(variant),
    }}}


def source_structures(source):
    native = process(
        source.source.decode(), ProcessConfig(language=source.language)
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


def coffee_features():
    features = {}
    for group in ("oo", "systems", "scripts"):
        path = Path(__file__).parent / f"coffee_features_{group}.json"
        features.update(json.loads(path.read_text(encoding="utf-8")))
    return features


def write_pipeline(language):
    bundle = coffee_pipeline(language)
    for seam in SEAMS:
        path = PIPELINE_ROOT / language / f"{seam}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(bundle[seam], ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8",
        )
