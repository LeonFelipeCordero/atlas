"""Negative/layout/mutation overlays have complete, grammar-correct snapshots."""

import json

import pytest

from tests.coffee_fixture import FIXTURE_ROOT
from tests.variant_snapshot_support import (
    VARIANT_ROOT, VARIANT_SNAPSHOT_ROOT, variant_groups, variant_snapshot,
)


@pytest.mark.parametrize("group", variant_groups())
def test_named_project_variants(group):
    actual = variant_snapshot(group)
    expected = json.loads((VARIANT_SNAPSHOT_ROOT / f"{group}.json").read_text())
    assert actual == expected
    for name, scenario in actual.items():
        assert_scenario_inputs((group, name), scenario)


def assert_scenario_inputs(identity, scenario):
    assert scenario["inputs"], identity
    assert {file["source"]["path"] for file in scenario["extraction"]} == set(scenario["structures"])
    for file in scenario["extraction"]:
        assert_source_bytes(identity, file)


def assert_source_bytes(identity, file):
    group, name = identity
    path = file["source"]["path"]
    source_path = VARIANT_ROOT / group / ("" if name == "file-boundaries" else name) / path
    if not source_path.exists():
        source_path = FIXTURE_ROOT / group / path
    assert bytes.fromhex(file["source"]["bytes"]["hex"]) == source_path.read_bytes()


def test_legacy_c_include_has_actual_grammar_and_native_spans():
    scenario = variant_snapshot("c")["legacy-scheduling-include"]
    record = scenario["native_only"]["scheduling.h"]
    content = (VARIANT_ROOT / "c/legacy-scheduling-include/scheduling.h").read_bytes()
    assert record["language"] == "c" and not record["has_error"]
    assert "preproc_include" in record["syntax"]
    pickup, wait = record["native"]
    assert (pickup["kind"], pickup["name"]) == ("struct", "ScheduledPickup")
    assert (wait["kind"], wait["name"]) == ("function", "scheduling_wait")
    assert content[pickup["span"]["start_byte"]:pickup["span"]["end_byte"]].startswith(b"struct ScheduledPickup {")
    assert b"difftime(pickup.ready, now)" in content[wait["span"]["start_byte"]:wait["span"]["end_byte"]]
    assert not scenario["extraction"]  # C remains excluded by the production importer.


def test_each_variant_group_has_a_snapshot():
    assert {path.stem for path in VARIANT_SNAPSHOT_ROOT.glob("*.json")} == set(variant_groups())
