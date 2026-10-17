"""Reviewed call targets from physical JVM coffee overload samples."""

from dataclasses import asdict
import json
from pathlib import Path

import pytest

from atlas.indexer import analyze_repository


ROOT = Path(__file__).parent


def selection_snapshot(language: str):
    graph = asdict(analyze_repository(ROOT / "code_samples" / language / "callable_selection"))
    nodes = {node["stableKey"]: node for node in graph["nodes"]}
    return [
        {
            "type": edge["type"],
            "line": edge["line"],
            "evidence": edge["evidence"],
            "target": nodes[edge["targetStableKey"]]["name"],
            "signature": nodes[edge["targetStableKey"]].get("signature"),
            "level": nodes[edge["targetStableKey"]]["level"],
        }
        for edge in graph["edges"]
        if edge["type"] in {"CALLS", "REFERENCES"}
    ]


@pytest.mark.parametrize("language", ["java", "kotlin"])
def test_jvm_callable_selection_snapshot(language):
    expected = json.loads((ROOT / "snapshots" / f"{language}_callable_selection.json").read_text())
    assert selection_snapshot(language) == expected
