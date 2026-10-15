"""The public registry is an explicit language/token coverage catalog."""

import pytest

from atlas.mutations import REGISTRY, validate_rules


def test_registry_contract() -> None:
    assert len({rule.id for rule in REGISTRY}) == len(REGISTRY)
    for rule in REGISTRY:
        assert rule.version == 1
        assert rule.limitations
        assert all(mapping.original != mapping.replacement for mapping in rule.mappings)
        validate_rules({rule.id: sorted({mapping.replacement for mapping in rule.mappings})})
    validate_rules({})
    validate_rules({"arithmetic.add-to-subtract": []})
    validate_rules({"arithmetic.add-to-subtract": ["-", "-"]})


@pytest.mark.parametrize("rules", [
    {"unknown": ["-"]},
    {"arithmetic.add-to-subtract": ["+"]},
    {"arithmetic.add-to-subtract": ["; execute()"]},
    {"comparison.equal-to-not-equal": ["!=="]},
    {"logical.strict-and-to-or": ["||"]},
    {"logical.truthy-and-to-or": ["or"]},
])
def test_invalid_selections(rules: dict[str, list[str]]) -> None:
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
