"""The same complete projects cover extraction, metrics, resolution and CLI."""

import json

import pytest

from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, coffee_graph, coffee_snapshot, coffee_sources
from tests.coffee_pipeline import GRAMMAR_VARIANTS, PIPELINE_ROOT, SEAMS, coffee_pipeline, project_cli
from tests.project_snapshot_support import structure_value


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("seam", SEAMS)
def test_complete_project_seam_snapshot(language, seam):
    expected = json.loads((PIPELINE_ROOT / language / f"{seam}.json").read_text())
    assert coffee_pipeline(language)[seam] == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_physical_source_reaches_every_analysis_seam(language):
    bundle = coffee_pipeline(language)
    sources = {source.path: source for source in coffee_sources(language)}
    assert set(sources) == physical_source_paths(language)
    files = {file["source"]["path"]: file for file in bundle["extraction"]["files"]}
    assert set(files) == set(sources) == set(bundle["extraction"]["structures"])
    graph_files = {node["path"] for node in bundle["graph"]["nodes"] if node["level"] == "file"}
    assert graph_files == set(sources)
    measurements = bundle["cli"]["report-json"]["output"]["nodes"]
    assert {node["path"] for node in measurements if node["level"] == "file"} == set(sources)
    assert_extraction_bytes(files, sources)
    assert_analysis_symbols(bundle, files)


def physical_source_paths(language):
    root = FIXTURE_ROOT / language
    return {path.relative_to(root).as_posix() for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts}


def assert_extraction_bytes(files, sources):
    for path, file in files.items():
        assert file["parse_error"] is None, path
        assert file["source"]["bytes"] == {"hex": sources[path].source.hex()}


def assert_analysis_symbols(bundle, files):
    assert {symbol["key"] for symbol in bundle["analysis"]["symbols"]} == {
        symbol["key"] for file in files.values() for symbol in file["declarations"]
    }


@pytest.mark.parametrize("language", LANGUAGES)
def test_staged_pipeline_matches_production_entry_point(language):
    assert coffee_pipeline(language)["graph"] == coffee_snapshot(coffee_graph(language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_tags_only_extraction_is_deterministic(language):
    for source in coffee_sources(language):
        structures = coffee_pipeline(language)["extraction"]["structures"][source.path]
        assert structure_value(extract_structure(ParsedSyntax(source), [])) == structures["tags_only"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_projects_are_not_artificial_threshold_padding(language):
    bundle = coffee_pipeline(language)
    for source in coffee_sources(language):
        assert len(source.source.splitlines()) <= 600, source.path
    assert all((symbol["line_count"] or 0) <= 100 for symbol in bundle["analysis"]["symbols"])


@pytest.mark.parametrize("language", LANGUAGES)
def test_project_cli_does_not_create_storage_or_modify_source(language, tmp_path, monkeypatch):
    database = tmp_path / "missing" / "atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    before = {source.path: source.source for source in coffee_sources(language)}
    assert project_cli(language) == coffee_pipeline(language)["cli"]
    assert not database.parent.exists()
    assert before == {source.path: source.source for source in coffee_sources(language)}


@pytest.mark.parametrize("case", [
    (language, path, grammar) for language, paths in GRAMMAR_VARIANTS.items()
    for path, grammars in paths.items() for grammar in grammars
])
def test_same_source_grammar_variants_are_identified_and_enriched(case):
    language, path, grammar = case
    extraction = coffee_pipeline(language)["extraction"]
    variant = extraction["grammar_variants"][path][grammar]
    source = next(source for source in coffee_sources(language) if source.path == path)
    assert variant["parser"]["source"]["language"] == grammar
    assert variant["parser"]["source"]["bytes"] == {"hex": source.source.hex()}
    assert variant["parser"]["parse_error"] is None
    assert {symbol["key"] for symbol in variant["parser"]["declarations"]} == {
        symbol["key"] for symbol in variant["analysis"]["symbols"]
    }
    assert all(symbol["language"] == grammar for symbol in variant["analysis"]["symbols"])


def test_each_physical_project_has_analysis_seams():
    assert {path.name for path in FIXTURE_ROOT.iterdir() if path.is_dir()} == set(LANGUAGES)


def test_shared_order_contract_has_real_tsx_parser_and_native_metadata():
    extraction = coffee_pipeline("typescript")["extraction"]
    original = next(file for file in extraction["files"] if file["source"]["path"] == "ordering/Order.ts")
    variant = extraction["grammar_variants"]["ordering/Order.ts"]["tsx"]
    assert variant["parser"]["source"]["language"] == "tsx"
    assert variant["parser"]["source"]["bytes"] == original["source"]["bytes"]
    assert variant["parser"]["parse_error"] is None
    assert [symbol["qualified_name"] for symbol in variant["parser"]["declarations"]] == [
        symbol["qualified_name"] for symbol in original["declarations"]
    ]
    assert set(variant["structures"]) == {"native", "tags_only", "merged"}
