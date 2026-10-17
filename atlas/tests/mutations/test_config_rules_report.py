"""Unit contracts for rule selection, catalog coverage, and report projection."""

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from atlas.domain.mutation_candidates import MutationCandidate
from atlas.mutations.config import MutationConfig
from atlas.mutations.manifests import MutationManifest
from atlas.mutations.report import build_mutation_report
from atlas.mutations.rules import REGISTRY, validate_rules


# These expectations must not be derived from the production catalog.
LANGUAGES = ("python", "javascript", "typescript", "tsx", "java", "kotlin", "rust", "go", "elixir")
NON_ELIXIR = ("python", "javascript", "typescript", "tsx", "java", "kotlin", "rust", "go")
STRICT_EQUALITY = ("javascript", "typescript", "tsx", "elixir")
PYTHON_LOGICAL = {"logical.and-to-or": ("and", "or"), "logical.or-to-and": ("or", "and")}
CATALOG = [
    ("arithmetic.add-to-subtract", "arithmetic", "+", "-", LANGUAGES),
    ("arithmetic.subtract-to-add", "arithmetic", "-", "+", LANGUAGES),
    ("arithmetic.multiply-to-divide", "arithmetic", "*", "/", LANGUAGES),
    ("arithmetic.divide-to-multiply", "arithmetic", "/", "*", LANGUAGES),
    ("comparison.equal-to-not-equal", "comparison", "==", "!=", LANGUAGES),
    ("comparison.not-equal-to-equal", "comparison", "!=", "==", LANGUAGES),
    ("comparison.less-to-less-equal", "comparison", "<", "<=", LANGUAGES),
    ("comparison.less-equal-to-less", "comparison", "<=", "<", LANGUAGES),
    ("comparison.greater-to-greater-equal", "comparison", ">", ">=", LANGUAGES),
    ("comparison.greater-equal-to-greater", "comparison", ">=", ">", LANGUAGES),
    ("comparison.less-to-greater", "comparison", "<", ">", LANGUAGES),
    ("comparison.greater-to-less", "comparison", ">", "<", LANGUAGES),
    ("comparison.strict-equal-to-strict-not-equal", "comparison", "===", "!==", STRICT_EQUALITY),
    ("comparison.strict-not-equal-to-strict-equal", "comparison", "!==", "===", STRICT_EQUALITY),
    ("logical.and-to-or", "logical", "&&", "||", NON_ELIXIR),
    ("logical.or-to-and", "logical", "||", "&&", NON_ELIXIR),
    ("logical.strict-and-to-or", "logical", "and", "or", ("elixir",)),
    ("logical.strict-or-to-and", "logical", "or", "and", ("elixir",)),
    ("logical.truthy-and-to-or", "logical", "&&", "||", ("elixir",)),
    ("logical.truthy-or-to-and", "logical", "||", "&&", ("elixir",)),
    ("assignment.add-to-subtract", "assignment", "+=", "-=", NON_ELIXIR),
    ("assignment.subtract-to-add", "assignment", "-=", "+=", NON_ELIXIR),
    ("assignment.multiply-to-divide", "assignment", "*=", "/=", NON_ELIXIR),
    ("assignment.divide-to-multiply", "assignment", "/=", "*=", NON_ELIXIR),
]


@pytest.fixture
def candidate_payload() -> Callable[..., dict[str, Any]]:
    def make(**overrides: Any) -> dict[str, Any]:
        span = {"startByte": 2, "endByte": 3, "startLine": 1, "startColumn": 3,
                "endLine": 1, "endColumn": 4}
        return {
            "id": "candidate-add", "path": "café.py", "language": "python", "sourceHash": "abc123",
            "kind": "arithmetic", "operator": "+", "span": span,
            "expressionSpan": {**span, "startByte": 0, "endByte": 5, "startColumn": 1, "endColumn": 6},
            "originalText": "+", "expressionText": "a + b", "callable": None,
            **overrides,
        }
    return make


@pytest.fixture
def manifest_payload(candidate_payload: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def make(**overrides: Any) -> dict[str, Any]:
        return {
            "id": "manifest-subtract", "candidateId": "candidate-add", "sourceHash": "abc123",
            "ruleId": "arithmetic.add-to-subtract", "ruleVersion": 1, "language": "python",
            "path": "café.py", "span": candidate_payload()["span"], "originalText": "+",
            "originalBytes": "Kw==", "replacement": "-", "replacementBytes": "LQ==",
            **overrides,
        }
    return make


def test_config_defaults_are_independent() -> None:
    # Given
    first, second = MutationConfig(), MutationConfig()

    # When
    first.rules.append("arithmetic.add-to-subtract")

    # Then
    assert first.model_dump() == {"rules": ["arithmetic.add-to-subtract"]}
    assert second.model_dump() == {"rules": []}


def test_config_preserves_selection_order_and_duplicates() -> None:
    # Given
    selected = ["logical.truthy-or-to-and", "arithmetic.add-to-subtract", "logical.truthy-or-to-and"]

    # When
    config = MutationConfig(rules=selected)

    # Then
    assert config.model_dump() == {"rules": selected}


@pytest.mark.parametrize("payload,error_type", [
    ({"rules": ("arithmetic.add-to-subtract",)}, "list_type"),
    ({"rules": {"arithmetic.add-to-subtract": "-"}}, "list_type"),
    ({"rules": "arithmetic.add-to-subtract"}, "list_type"),
    ({"rules": None}, "list_type"),
    ({"rules": [1]}, "string_type"),
    ({"rules": [b"arithmetic.add-to-subtract"]}, "string_type"),
    ({"rules": ["arithmetic.add-to-subtract", "unknown"]}, "value_error"),
    ({"replacement": "-"}, "extra_forbidden"),
])
def test_config_rejects_invalid_selection(payload: dict[str, Any], error_type: str) -> None:
    # Given / When
    with pytest.raises(ValidationError) as caught:
        MutationConfig.model_validate(payload)

    # Then
    assert caught.value.errors()[0]["type"] == error_type


def test_catalog_has_exact_rule_ids_without_duplicates() -> None:
    # Given
    expected = {row[0] for row in CATALOG}

    # When
    ids = [rule.id for rule in REGISTRY]

    # Then
    assert set(ids) == expected
    assert len(ids) == len(expected)


@pytest.mark.parametrize("entry", CATALOG, ids=[row[0] for row in CATALOG])
def test_catalog_has_exact_language_token_mappings(entry: tuple[str, str, str, str, tuple[str, ...]]) -> None:
    # Given
    rule_id, kind, original, replacement, languages = entry
    expected = {language: (original, replacement) for language in languages}
    if rule_id in PYTHON_LOGICAL:
        expected["python"] = PYTHON_LOGICAL[rule_id]

    # When
    rule = next(rule for rule in REGISTRY if rule.id == rule_id)

    # Then
    assert rule.kind == kind
    assert rule.version == 1
    assert sorted((m.language, m.original, m.replacement) for m in rule.mappings) == sorted(
        (language, *tokens) for language, tokens in expected.items()
    )


@pytest.mark.parametrize("rules", [[], [row[0] for row in CATALOG],
                                   ["arithmetic.add-to-subtract", "arithmetic.add-to-subtract"]])
def test_validate_rules_accepts_known_selections_without_mutating_them(rules: list[str]) -> None:
    # Given
    before = rules.copy()

    # When
    result = validate_rules(rules)

    # Then
    assert result is None
    assert rules == before


@pytest.mark.parametrize("rules,message", [
    (None, "Mutation rules must be a list of rule IDs"),
    ("arithmetic.add-to-subtract", "Mutation rules must be a list of rule IDs"),
    (("arithmetic.add-to-subtract",), "Mutation rules must be a list of rule IDs"),
    ({}, "Mutation rules must be a list of rule IDs"),
    (["arithmetic.add-to-subtract", "unknown"], "Unknown mutation rule: unknown"),
    ([1], "Unknown mutation rule: 1"),
    ([["arithmetic.add-to-subtract"]], "Unknown mutation rule: ['arithmetic.add-to-subtract']"),
])
def test_validate_rules_rejects_invalid_runtime_inputs(rules: Any, message: str) -> None:
    # Given / When
    with pytest.raises(ValueError) as caught:
        validate_rules(rules)

    # Then
    assert str(caught.value) == message


def test_report_validates_candidates_and_serializes_real_manifests(
    tmp_path: Path, candidate_payload: Callable[..., dict[str, Any]],
    manifest_payload: Callable[..., dict[str, Any]],
) -> None:
    # Given
    payloads = [candidate_payload(), candidate_payload(id="candidate-second", path="other.py")]
    report = {"schemaVersion": 99, "mutationCandidates": payloads, "summary": {"files": 2}}
    original = deepcopy(report)
    config = MutationConfig(rules=["arithmetic.subtract-to-add", "arithmetic.add-to-subtract"])
    expected = [manifest_payload(id="second", candidateId="candidate-second", path="other.py"),
                manifest_payload()]
    manifests = [MutationManifest.model_validate(item) for item in expected]

    # When
    with patch("atlas.mutations.report.generate_manifests", autospec=True, return_value=manifests) as generate:
        result = build_mutation_report(tmp_path, report, config)

    # Then
    generate.assert_called_once_with(tmp_path, [MutationCandidate.model_validate(item) for item in payloads],
                                     ["arithmetic.subtract-to-add", "arithmetic.add-to-subtract"])
    assert all(isinstance(item, MutationCandidate) for item in generate.call_args.args[1])
    assert result == {"schemaVersion": 1, "mutations": expected}
    assert report == original
    assert config.rules == ["arithmetic.subtract-to-add", "arithmetic.add-to-subtract"]


@pytest.mark.parametrize("has_candidates", [False, True])
def test_disabled_report_still_delegates_validation_and_emits_empty_output(
    tmp_path: Path, candidate_payload: Callable[..., dict[str, Any]], has_candidates: bool,
) -> None:
    # Given
    payloads = [candidate_payload()] if has_candidates else []
    report = {"mutationCandidates": payloads}

    # When
    with patch("atlas.mutations.report.generate_manifests", autospec=True, return_value=[]) as generate:
        result = build_mutation_report(tmp_path, report, MutationConfig())

    # Then
    generate.assert_called_once_with(tmp_path, [MutationCandidate.model_validate(item) for item in payloads], [])
    assert result == {"schemaVersion": 1, "mutations": []}


@pytest.mark.parametrize("overrides", [{"id": None}, {"span": {"startByte": 2}}, {"kind": "unknown"}])
def test_report_rejects_malformed_candidates_before_generation(
    tmp_path: Path, candidate_payload: Callable[..., dict[str, Any]], overrides: dict[str, Any],
) -> None:
    # Given
    report = {"mutationCandidates": [candidate_payload(), candidate_payload(**overrides)]}

    # When
    with patch("atlas.mutations.report.generate_manifests", autospec=True) as generate:
        with pytest.raises(ValidationError):
            build_mutation_report(tmp_path, report, MutationConfig())

    # Then
    generate.assert_not_called()


def test_report_propagates_manifest_validation_failure(
    tmp_path: Path, candidate_payload: Callable[..., dict[str, Any]],
) -> None:
    # Given
    report = {"mutationCandidates": [candidate_payload()]}
    original = deepcopy(report)
    error = ValueError("Stale or invalid mutation candidate")

    # When
    with patch("atlas.mutations.report.generate_manifests", autospec=True, side_effect=error) as generate:
        with pytest.raises(ValueError) as caught:
            build_mutation_report(tmp_path, report, MutationConfig())

    # Then
    generate.assert_called_once()
    assert caught.value is error
    assert report == original
