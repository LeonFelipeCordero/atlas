"""Independent safety regressions through the production coffee pipeline."""

import json
from pathlib import Path

import pytest

from atlas.indexer import analyze_repository

ROOT = Path(__file__).parent
LANGUAGES = ("java", "kotlin", "python", "javascript", "typescript")


def safety_snapshot(language):
    artifact = analyze_repository(ROOT / "fixtures/coffee/safety_review" / language)
    nodes = {node["stableKey"]: node for node in artifact.nodes}
    return [
        {
            "source": nodes[edge["sourceStableKey"]]["qualifiedName"],
            "evidence": edge["evidence"],
            "target": nodes[edge["targetStableKey"]]["qualifiedName"],
            "signature": nodes[edge["targetStableKey"]].get("signature"),
            "targetLine": nodes[edge["targetStableKey"]].get("startLine"),
        }
        for edge in artifact.edges if edge["type"] == "CALLS"
    ]


@pytest.mark.parametrize("language", LANGUAGES)
def test_safety_review_snapshot(language):
    expected = json.loads((ROOT / "snapshots/safety_review" / f"{language}.json").read_text())
    assert safety_snapshot(language) == expected


@pytest.mark.parametrize("language", ("python", "javascript", "typescript"))
def test_script_safety_review_targets(language):
    ext = {"python": "py", "javascript": "js", "typescript": "ts"}[language]
    prefix = "" if language == "python" else "new "
    calls = {edge["evidence"]: edge["target"] for edge in safety_snapshot(language)
             if edge["source"] == f"safety.{ext}::serve"}
    unsafe = ["AliasWrite", "AliasMutator", "AliasOverride"]
    if language == "python":
        unsafe += ["DecoratedBase", "DecoratedChild", "DecoratedGrandchild"]
    else:
        unsafe += ["FieldOverride"]
    for owner in unsafe:
        assert calls[f"{prefix}{owner}().brew(order)"] == f"external:{language}:brew"
    for owner in ("Pickup", "SafeAlias"):
        assert calls[f"{prefix}{owner}().brew(order)"] == f"safety.{ext}::Brewing.brew"
    if language == "python":
        assert calls["PlainGrandchild().brew(order)"] == "safety.py::PlainBase.brew"
    else:
        assert calls["new StaticFieldOverride().brew(order)"] == f"safety.{ext}::StaticFieldOverride.brew"
