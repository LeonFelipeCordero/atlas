"""Persist symbol classification through service summaries, not storage internals."""

from pathlib import Path
from typing import Any

import pytest

from atlas.services.factories import repository_service


@pytest.mark.parametrize("scenario", [
    ({"level": "type", "kind": "class"}, 1),
    ({"level": "callable", "kind": "function"}, 1),
    ({"level": "symbol", "kind": "variable"}, 1),
    ({"level": "module", "kind": "namespace"}, 1),
    ({"level": "module", "kind": "directory"}, 0),
    ({"level": "module", "kind": "folder"}, 0),
    ({"level": "file", "kind": "namespace"}, 0),
    ({"signature": "brew()"}, 1),
    ({"startLine": 3}, 1),
    ({"properties": {"visibility": "public"}}, 1),
    ({"properties": {"decorators": ["cached"]}}, 1),
    ({"properties": {"decorators": None}}, 1),
])
def test_symbol_classification_survives_persistence(database: Path, tmp_path: Path, scenario: tuple[dict[str, Any], int]) -> None:
    overrides, expected = scenario
    node = {"stableKey": "node", "type": "file", "level": "file", "kind": "file", "name": "coffee", "path": "coffee.py", **overrides}
    with repository_service(database) as repositories:
        saved = repositories.save_folder(tmp_path, {"nodes": [node], "edges": []})
    with repository_service(database) as repositories:
        graph = repositories.get_architecture(saved.repositoryId)
        assert graph is not None
        assert graph.stats.symbols == expected
        facts = repositories.get_report_facts(saved.repositoryId)
        assert facts is not None
        assert len(facts.nodes) == 1
        assert facts.nodes[0].startLine == overrides.get("startLine")
