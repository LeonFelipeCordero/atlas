"""Coverage contracts must reject regressions even if golden files are updated."""

from copy import deepcopy

import pytest

from tests.coffee_feature_assertions import assert_feature_contract, assert_project_sources
from tests.coffee_pipeline import coffee_features, coffee_pipeline
from tests.coffee_scenarios import DECLARATIONS


def feature_context(name):
    feature = next(feature for feature in coffee_features()["python"] if feature["feature"] == name)
    bundle = deepcopy(coffee_pipeline("python"))
    files = {file["source"]["path"]: file for file in bundle["extraction"]["files"]}
    matches = [symbol for symbol in files[feature["path"]]["declarations"]
               if symbol["qualified_name"].endswith("::" + feature["symbol"])]
    return feature, bundle, matches


def test_receiver_or_extra_input_cannot_pass_exact_parameter_contract():
    feature, bundle, matches = feature_context("eight-input-calibration")
    symbol = next(symbol for symbol in bundle["analysis"]["symbols"] if symbol["key"] == matches[0]["key"])
    symbol["parameter_count"] = 9
    with pytest.raises(AssertionError):
        assert_feature_contract(matches, bundle, feature)


def test_generic_inheritance_cannot_disappear_behind_the_same_symbol_name():
    feature, bundle, matches = feature_context("generic-inheritance")
    symbol = next(symbol for symbol in bundle["analysis"]["symbols"] if symbol["key"] == matches[0]["key"])
    symbol["signature"] = "class Inventory:"
    with pytest.raises(AssertionError):
        assert_feature_contract(matches, bundle, feature)


def test_recursive_relationship_cannot_disappear_behind_the_same_symbol_name():
    feature, bundle, matches = feature_context("recursive-retry")
    bundle["analysis"]["resolved"]["connections"] = []
    with pytest.raises(AssertionError):
        assert_feature_contract(matches, bundle, feature)


def test_discovery_omissions_cannot_remove_a_file_from_both_sides_of_coverage():
    bundle = deepcopy(coffee_pipeline("python"))
    bundle["extraction"]["files"] = [file for file in bundle["extraction"]["files"]
                                      if file["source"]["path"] != "src/coffee/reporting/report.py"]
    with pytest.raises(AssertionError):
        assert_project_sources(bundle, set(DECLARATIONS["python"]))


@pytest.mark.parametrize("seam", ["graph", "cli"])
def test_feature_must_reach_graph_and_cli_not_just_the_parser(seam):
    feature, bundle, matches = feature_context("eight-input-calibration")
    if seam == "graph":
        bundle["graph"]["edges"] = []
        bundle["graph"]["nodes"] = []
    else:
        bundle["cli"]["report-json"]["output"]["nodes"] = []
    with pytest.raises((AssertionError, KeyError)):
        assert_feature_contract(matches, bundle, feature)
