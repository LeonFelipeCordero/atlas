"""Edge cases are physical sources in the same projects as the main snapshots."""

import pytest

from atlas.parsing.discovery import detect_language
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, coffee_graph
from tests.coffee_pipeline import coffee_pipeline


@pytest.mark.parametrize("language", LANGUAGES)
def test_edge_cases_reach_complete_project_snapshots(language):
    extraction = coffee_pipeline(language)["extraction"]
    root = FIXTURE_ROOT / language
    physical = physical_edge_paths(root)
    files = {file["source"]["path"]: file for file in extraction["files"]}
    excluded = extraction["excluded_sources"]
    assert physical
    assert physical == {path for path in files if path.startswith("edge_cases/")} | set(excluded)
    for path in physical:
        record = files[path]["source"] if path in files else excluded[path]
        assert bytes.fromhex(record["bytes"]["hex"]) == (root / path).read_bytes()


def physical_edge_paths(root):
    return {path.relative_to(root).as_posix() for path in (root / "edge_cases").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts}


def test_legacy_c_include_has_actual_grammar_and_native_spans():
    path = "edge_cases/c/legacy-scheduling-include/scheduling.h"
    record = coffee_pipeline("python")["extraction"]["excluded_sources"][path]["native_only"]
    content = (FIXTURE_ROOT / "python" / path).read_bytes()
    assert record["language"] == "c" and not record["has_error"]
    assert "preproc_include" in record["syntax"]
    pickup, wait = record["native"]
    assert (pickup["kind"], pickup["name"]) == ("struct", "ScheduledPickup")
    assert (wait["kind"], wait["name"]) == ("function", "scheduling_wait")
    assert content[pickup["span"]["start_byte"]:pickup["span"]["end_byte"]].startswith(b"struct ScheduledPickup {")
    assert b"difftime(pickup.ready, now)" in content[wait["span"]["start_byte"]:wait["span"]["end_byte"]]
    assert detect_language(FIXTURE_ROOT / "python" / path) is None


@pytest.mark.parametrize("name", ["legacy.php", "Legacy.cs", "legacy.rb"])
def test_excluded_languages_stay_out_of_complete_project(name):
    prefix = "edge_cases/operational/excluded-languages/"
    path = prefix + name
    assert (FIXTURE_ROOT / "python" / path).is_file()
    assert detect_language(FIXTURE_ROOT / "python" / path) is None
    extraction = coffee_pipeline("python")["extraction"]
    assert path in extraction["excluded_sources"]
    assert path not in {file["source"]["path"] for file in extraction["files"]}
    graph = coffee_graph("python")
    files = {node["path"] for node in graph.nodes if node["level"] == "file"}
    assert path not in files
    assert prefix + "dispatch.lua" in files
