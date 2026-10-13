"""Standalone receiver/member snapshots from production-indexed script coffee."""

import json

import pytest

from atlas.indexer import analyze_repository
from tests.coffee_fixture import FIXTURE_ROOT, SNAPSHOT_ROOT

LANGUAGES = ("python", "javascript", "typescript", "tsx")


def script_member_snapshot(language):
    artifact = analyze_repository(FIXTURE_ROOT / "script_members" / language)
    nodes = {node["stableKey"]: node for node in artifact.nodes}
    return [
        {
            "source": nodes[edge["sourceStableKey"]]["qualifiedName"],
            "evidence": edge["evidence"],
            "target": nodes[edge["targetStableKey"]]["qualifiedName"],
            "targetLine": nodes[edge["targetStableKey"]].get("startLine"),
            "confidence": edge["confidence"],
        }
        for edge in artifact.edges
        if edge["type"] in {"CALLS", "INHERITS"}
    ]


@pytest.mark.parametrize("language", LANGUAGES)
def test_script_members_match_standalone_snapshot(language):
    actual = script_member_snapshot(language)
    expected = json.loads((SNAPSHOT_ROOT / "script_members" / f"{language}.json").read_text())
    assert actual == expected
    calls = {row["evidence"]: row for row in actual}
    prefix = "" if language == "python" else "new "
    assert calls[f"{prefix}Pickup().brew(order)"]["target"].endswith("::Brewing.brew")
    assert calls[f"{prefix}Window().brew(order)"]["target"].endswith("::Brewing.brew")
    assert calls[f"{prefix}Delivery().brew(order)"]["target"].endswith("::Delivery.brew")
    assert "vendor" in calls[f"{prefix}ImportedPickup().brew(order)"]["target"]
    for owner in ("Unknown", "Mutated", "Masked", "PatchedPickup", "CycleA", "Initialized"):
        assert calls[f"{prefix}{owner}().brew(order)"]["target"] == f"external:{language}:brew"
    assert calls["ledger.brew(order)"]["target"] == f"external:{language}:brew"
    if language == "javascript":
        prices = [calls[f"new Menu().price({args})"] for args in ("", "order", "order, 1, 2")]
        assert len({(row["target"], row["targetLine"]) for row in prices}) == 1
        assert prices[0]["targetLine"] == 18  # Last executable method, not the one-arg body.
    else:
        assert calls[f"{prefix}Repeated().price(order)"]["target"] == f"external:{language}:price"
        assert calls[f"{prefix}SignaturesOnly().price(order)"]["target"] == f"external:{language}:price"
        assert calls[f"{prefix}Menu().price(order)"]["target"].endswith("::Menu.price")
        assert calls["quote(order)"]["target"].endswith("::quote")
        assert calls[f"{prefix}Menu().price(order)"]["targetLine"] == (50 if language == "python" else 19)
        assert calls["quote(order)"]["targetLine"] == (62 if language == "python" else 23)
    if language == "python":
        for owner in ("Ambiguous", "Dynamic", "Partial"):
            assert calls[f"{owner}().brew(order)"]["target"] == "external:python:brew"
        assert calls["Untrusted().price(order)"]["target"] == "external:python:price"
        assert calls["AmbiguousOverride().brew(order)"]["target"].endswith("::AmbiguousOverride.brew")
    else:
        for owner in ("Dynamic", "CalledBase"):
            assert calls[f"new {owner}().brew(order)"]["target"] == f"external:{language}:brew"
