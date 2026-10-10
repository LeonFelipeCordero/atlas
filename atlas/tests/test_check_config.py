"""Project config is flat, defaults are explicit, and null disables a rule."""

import json
from pathlib import Path

import pytest

from atlas.metrics.config import CheckConfig, load_config

DEFAULTS = {
    "maxFileLines": 600, "maxFunctionLines": 100, "maxParameters": 3,
    "maxWeightedComplexity": 8, "maxDecisionDepth": 3, "maxNestedLoops": 0,
    "maxCircularImportGroups": 0, "maxChangeImpact": None, "maxInstability": None,
}


def test_missing_config_and_empty_object_use_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path).model_dump() == DEFAULTS
    (tmp_path / "atlas.json").write_text("{}")
    assert load_config(tmp_path).model_dump() == DEFAULTS


def test_partial_overrides_and_null_disabled_limits(tmp_path: Path) -> None:
    overrides = {"maxParameters": 5, "maxNestedLoops": None, "maxChangeImpact": 4, "maxInstability": 0.8}
    (tmp_path / "atlas.json").write_text(json.dumps(overrides))
    assert load_config(tmp_path).model_dump() == {**DEFAULTS, **overrides}


@pytest.mark.parametrize("key", DEFAULTS)
def test_every_rule_can_be_disabled(key: str) -> None:
    assert getattr(CheckConfig.model_validate({key: None}), key) is None


@pytest.mark.parametrize("source", [
    "{", "null", "[]", "1", '{"maxFanOut": 10}', '{"maxCyclomaticComplexity": 8}',
    '{"maxParameters": true}', '{"maxParameters": "3"}', '{"maxParameters": 3.5}',
    '{"maxParameters": -1}', '{"maxInstability": -0.1}', '{"maxInstability": 1.1}',
    '{"maxInstability": true}', '{"maxInstability": NaN}', '{"maxInstability": Infinity}',
])
def test_invalid_configuration_is_an_error_with_its_path(tmp_path: Path, source: str) -> None:
    path = tmp_path / "atlas.json"
    path.write_text(source)
    with pytest.raises(ValueError, match="Invalid .*atlas.json"):
        load_config(tmp_path)


def test_root_configuration_does_not_search_parent_folders(tmp_path: Path) -> None:
    (tmp_path / "atlas.json").write_text('{"maxParameters": 99}')
    project = tmp_path / "project"
    project.mkdir()
    assert load_config(project).maxParameters == 3
