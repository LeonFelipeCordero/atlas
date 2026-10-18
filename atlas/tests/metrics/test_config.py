"""Strict project limits and local configuration loading."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas.metrics.config import CheckConfig, ProjectConfig, load_config, load_project_config


DEFAULTS = {
    "maxFileLines": 600, "maxFunctionLines": 100, "maxParameters": 3,
    "maxWeightedComplexity": 8, "maxDecisionDepth": 3, "maxNestedLoops": 0,
    "maxCircularImportGroups": 0, "maxChangeImpact": None, "maxInstability": None,
}


def test_missing_config_uses_defaults_without_searching_parents(tmp_path: Path) -> None:
    (tmp_path / "atlas.json").write_text('{"maxFileLines": 1}')
    child = tmp_path / "child"
    child.mkdir()

    result = load_project_config(child)

    assert result.model_dump() == {**DEFAULTS, "mutations": {"rules": [], "targets": {}}}


def test_load_checks_excludes_mutation_settings_and_preserves_overrides(tmp_path: Path) -> None:
    (tmp_path / "atlas.json").write_text(json.dumps({
        "maxFileLines": None, "maxParameters": 0, "maxInstability": 0.25,
        "maxChangeImpact": 2, "mutations": {"rules": []},
    }))

    result = load_config(tmp_path)

    assert type(result) is CheckConfig
    assert result.model_dump() == {
        **DEFAULTS, "maxFileLines": None, "maxParameters": 0,
        "maxInstability": 0.25, "maxChangeImpact": 2,
    }


@pytest.mark.parametrize("name", [name for name in DEFAULTS if name != "maxInstability"])
@pytest.mark.parametrize("value", [-1, True, "2", 2.5])
def test_count_limits_reject_negative_or_coerced_values(name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CheckConfig.model_validate({name: value})


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf"), float("nan"), "0.5", True])
def test_instability_rejects_out_of_range_nonfinite_and_coerced_values(value: object) -> None:
    with pytest.raises(ValidationError):
        CheckConfig.model_validate({"maxInstability": value})


@pytest.mark.parametrize("value", [0.0, 1.0, None])
def test_instability_accepts_closed_boundaries_and_disabled(value: float | None) -> None:
    assert CheckConfig(maxInstability=value).maxInstability == value


def test_all_count_limits_accept_zero() -> None:
    values = {name: 0.0 if name == "maxInstability" else 0 for name in DEFAULTS}

    result = CheckConfig.model_validate(values)

    assert result.model_dump() == values


def test_all_limits_can_be_disabled() -> None:
    values = dict.fromkeys(DEFAULTS)

    result = CheckConfig.model_validate(values)

    assert result.model_dump() == values


@pytest.mark.parametrize("source", ['{', '{"unknown": 1}', '{"maxFileLines": -1}',
                                    '{"mutations": {"rules": ["unknown-rule"]}}'])
def test_invalid_project_config_has_path_and_original_cause(tmp_path: Path, source: str) -> None:
    path = tmp_path / "atlas.json"
    path.write_text(source)

    with pytest.raises(ValueError, match="Invalid " + str(path)) as caught:
        load_project_config(tmp_path)

    assert isinstance(caught.value.__cause__, ValidationError)


def test_io_errors_are_not_reported_as_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "atlas.json").mkdir()

    with pytest.raises(IsADirectoryError):
        load_project_config(tmp_path)


def test_unknown_fields_are_rejected_by_both_models() -> None:
    for model in (CheckConfig, ProjectConfig):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            model.model_validate({"maxFileLine": 10})
