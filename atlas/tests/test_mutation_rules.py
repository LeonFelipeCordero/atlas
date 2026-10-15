"""The public registry is an explicit language/token coverage catalog."""

import pytest

from atlas.mutations import REGISTRY, validate_rules
from atlas.mutations.rules import MutationRule


@pytest.mark.parametrize("rule", REGISTRY, ids=lambda rule: rule.id)
def test_registry_contract(rule: MutationRule) -> None:
    assert rule.version == 1
    assert rule.limitations
    assert all(mapping.original != mapping.replacement for mapping in rule.mappings)
    validate_rules([rule.id])


def test_registry_selections() -> None:
    assert len({rule.id for rule in REGISTRY}) == len(REGISTRY)
    assert len(REGISTRY) == 24
    validate_rules([])
    validate_rules(["arithmetic.add-to-subtract"])
    validate_rules(["arithmetic.add-to-subtract", "arithmetic.add-to-subtract"])


@pytest.mark.parametrize("rules", [
    ["unknown"], ["+"], ["; execute()"],
    {"arithmetic.add-to-subtract": ["-"]},
    "arithmetic.add-to-subtract", [False],
])
def test_invalid_selections(rules: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_rules(rules)


def test_coverage_is_deliberate() -> None:
    catalog = {rule.id: rule for rule in REGISTRY}
    assert {mapping.language for mapping in catalog["arithmetic.add-to-subtract"].mappings} == {
        "python", "javascript", "typescript", "tsx", "java", "kotlin", "rust", "go", "elixir",
    }
    assert "python" not in {mapping.language for mapping in catalog["comparison.strict-equal-to-strict-not-equal"].mappings}
    assert all(mapping.language == "elixir" for mapping in catalog["logical.strict-and-to-or"].mappings)
    assert all(rule.kind != "condition" for rule in REGISTRY)
    assert all(mapping.language != "elixir" for mapping in catalog["assignment.add-to-subtract"].mappings)
