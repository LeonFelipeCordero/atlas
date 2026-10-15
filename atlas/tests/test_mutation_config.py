"""Mutation selections share atlas.json without becoming quantitative checks."""

import json
from pathlib import Path

import pytest

from atlas.metrics.config import load_config, load_project_config
from atlas.mutations.config import MutationConfig


def test_default_and_partial_project_configuration(tmp_path: Path) -> None:
    assert load_project_config(tmp_path).mutations.rules == {}
    (tmp_path / "atlas.json").write_text(json.dumps({
        "maxParameters": 5,
        "mutations": {"rules": {"arithmetic.add-to-subtract": ["-", "-"]}},
    }))
    assert load_project_config(tmp_path).mutations.rules == {"arithmetic.add-to-subtract": ["-", "-"]}
    checks = load_config(tmp_path)
    assert checks.maxParameters == 5
    assert "mutations" not in checks.model_dump()


def test_disabled_rules_and_no_parent_lookup(tmp_path: Path) -> None:
    assert MutationConfig(rules={"arithmetic.add-to-subtract": []}).rules == {"arithmetic.add-to-subtract": []}
    (tmp_path / "atlas.json").write_text('{"mutations":{"rules":{"arithmetic.add-to-subtract":["-"]}}}')
    child = tmp_path / "child"
    child.mkdir()
    assert load_project_config(child).mutations.rules == {}


@pytest.mark.parametrize("mutations", [
    None, [], {"unknown": {}}, {"rules": {"unknown": []}},
    {"rules": {"arithmetic.add-to-subtract": ["generated()"]}},
    {"rules": {"arithmetic.add-to-subtract": "-"}},
    {"rules": {"arithmetic.add-to-subtract": [False]}},
])
def test_invalid_mutation_configuration_has_path(tmp_path: Path, mutations: object) -> None:
    (tmp_path / "atlas.json").write_text(json.dumps({"mutations": mutations}))
    with pytest.raises(ValueError, match="Invalid .*atlas.json"):
        load_project_config(tmp_path)
    with pytest.raises(ValueError, match="Invalid .*atlas.json"):
        load_config(tmp_path)
