"""One shared project covers parsing, native metadata, metrics, resolution and CLI."""

import json

import pytest

from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_feature_assertions import assert_feature_contract, assert_project_sources
from tests.coffee_fixture import LANGUAGES, coffee_graph, coffee_snapshot, coffee_sources
from tests.coffee_scenarios import DECLARATIONS
from tests.coffee_pipeline import PIPELINE_ROOT, SEAMS, coffee_features, coffee_pipeline, project_cli
from tests.parsing_snapshot_support import structure_value

FEATURES = [(language, feature) for language, features in coffee_features().items() for feature in features]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("seam", SEAMS)
def test_complete_project_seam_snapshot(language, seam):
    expected = json.loads((PIPELINE_ROOT / language / f"{seam}.json").read_text())
    assert coffee_pipeline(language)[seam] == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_source_reaches_the_snapshots(language):
    extraction = coffee_pipeline(language)["extraction"]
    files = {file["source"]["path"]: file for file in extraction["files"]}
    expected = set(DECLARATIONS[language])
    assert_project_sources(coffee_pipeline(language), expected)
    assert {source.path for source in coffee_sources(language)} == expected
    assert all(file["parse_error"] is None for file in files.values())
    features = coffee_features()[language]
    assert len({feature["feature"] for feature in features}) == len(features)


@pytest.mark.parametrize("case", FEATURES, ids=[f"{language}-{feature['feature']}" for language, feature in FEATURES])
def test_every_language_feature_reaches_all_analysis_seams(case):
    language, feature = case
    bundle = coffee_pipeline(language)
    file = next(file for file in bundle["extraction"]["files"] if file["source"]["path"] == feature["path"])
    matches = [symbol for symbol in file["declarations"]
               if symbol["qualified_name"].split("::", 1)[1] == feature["symbol"]]
    assert matches, feature
    assert all(symbol["complexity"] is None for symbol in matches), feature
    assert_feature_contract(matches, bundle, feature)
    assert_structure_feature(bundle["extraction"]["structures"][feature["path"]], feature)


def structure_names(items, prefix=""):
    names = set()
    for item in items:
        name = f"{prefix}.{item['name'] or '<anonymous>'}".lstrip(".")
        names.add(name)
        names.update(structure_names(item["children"], name))
    return names


def assert_structure_feature(structures, feature):
    assert feature["symbol"] in structure_names(structures["merged"]), feature
    # Pin native-only enum/constructor records and Rust impl ownership differences.
    expected = feature.get("tagsOnlySymbol", feature["symbol"])
    names = structure_names(structures["tags_only"])
    if expected is None:
        assert feature["symbol"] not in names, feature
    else:
        assert expected in names, feature


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


def test_shared_order_contract_has_a_real_tsx_parser_and_native_metadata_baseline():
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


def test_language_matrix_has_feature_and_snapshot_coverage():
    assert set(coffee_features()) == set(LANGUAGES)
    assert {path.name for path in PIPELINE_ROOT.iterdir() if path.is_dir()} == set(LANGUAGES)


@pytest.mark.parametrize("language", LANGUAGES)
def test_project_has_every_seam_baseline(language):
    assert {path.stem for path in (PIPELINE_ROOT / language).glob("*.json")} == set(SEAMS)
