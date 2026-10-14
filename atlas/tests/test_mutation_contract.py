"""Versioned evidence validation checks structure, never execution truth."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas.domain.mutation import MutationTrialInput
from tests.mutation_support import trial_input


@pytest.mark.parametrize("outcome,exit_code", [("killed", 1), ("survived", 0), ("invalid", 2), ("timeout", None), ("error", None)])
def test_supported_experiment_outcomes(outcome: str, exit_code: int | None) -> None:
    data = trial_input().model_dump()
    data["outcome"] = outcome
    data["mutant"]["exit_code"] = exit_code
    assert MutationTrialInput.model_validate(data).outcome == outcome


def test_skipped_and_baseline_error_need_explanation_not_mutant_evidence() -> None:
    data = trial_input().model_dump()
    data.update(outcome="skipped", patch="", baseline=None, mutant=None)
    assert MutationTrialInput.model_validate(data).outcome == "skipped"
    data.update(outcome="error", baseline={"command": "pytest", "exit_code": 2, "duration_seconds": 0.1, "log_reference": "baseline.log"})
    assert MutationTrialInput.model_validate(data).outcome == "error"


@pytest.mark.parametrize("change", [
    {"schema_version": 2}, {"outcome": "verified"}, {"unexpected": "field"},
    {"hypothesis": ""}, {"explanation": ""}, {"baseline": None}, {"mutant": None}, {"patch": ""},
])
def test_invalid_contracts_are_rejected(change: dict) -> None:
    with pytest.raises(ValidationError):
        MutationTrialInput.model_validate({**trial_input().model_dump(), **change})


@pytest.mark.parametrize("section,key,value", [
    ("baseline", "exit_code", 1), ("baseline", "duration_seconds", -1),
    ("baseline", "duration_seconds", float("inf")), ("mutant", "log_reference", ""),
    ("mutant", "exit_code", 1), ("source_identity", "original_file_hash", "sha256?"),
    ("source_identity", "mutant_file_hash", None), ("source_identity", "restored_file_hash", None),
])
def test_evidence_constraints(section: str, key: str, value: object) -> None:
    data = trial_input().model_dump()
    data[section][key] = value
    with pytest.raises(ValidationError):
        MutationTrialInput.model_validate(data)


@pytest.mark.parametrize("exit_code", [0, None])
def test_kill_requires_failing_execution_but_does_not_certify_assertions(exit_code: int | None) -> None:
    data = trial_input().model_dump()
    data["outcome"] = "killed"
    data["mutant"]["exit_code"] = exit_code
    with pytest.raises(ValidationError, match="failing mutant"):
        MutationTrialInput.model_validate(data)


def test_bundled_example_matches_version_one_contract() -> None:
    path = Path(__file__).resolve().parents[2] / "examples/mutation/trial-v1.json"
    data = json.loads(path.read_text())
    assert MutationTrialInput.model_validate(data).schema_version == 1
    assert "Illustrative" in data["explanation"]
