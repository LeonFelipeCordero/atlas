"""Registry-selected metric policies retain language-specific syntax semantics."""

import pytest

from atlas.metrics.adapters import (
    get_metric_adapter,
    get_resolution_adapter,
    receiver_coverage,
)
from atlas.metrics.adapters.base import COMMON_METRICS
from tests.metrics.adapter_support import node


@pytest.mark.parametrize(
    ("language", "expression", "expected"),
    [
        ("rust", node("match_arm", pattern=node(value="_")), False),
        ("rust", node("match_arm", pattern=node(value="Some(x)")), True),
        (
            "python",
            node(
                "case_clause",
                children=[node("case_pattern", children=[node("_")], named=[])],
            ),
            False,
        ),
        ("elixir", node("call", target=node(value="unless")), True),
        ("javascript", node("switch_case", children=[node("default")]), False),
        ("lua", node("match_arm", pattern=node(value="_")), False),
    ],
)
def test_registry_metric_decisions_use_language_overrides(
    language, expression, expected
):
    assert get_metric_adapter(language).metrics.decision(expression) is expected


@pytest.mark.parametrize("shape", ["direct", "else_clause", "unrelated"])
def test_else_if_alternative_requires_conditional_owner(shape):
    branch = node("if_statement")
    if shape == "direct":
        node("if_statement", alternative=branch)
    else:
        clause = node("else_clause", children=[branch])
        node("if_statement" if shape == "else_clause" else "block", children=[clause])
    assert COMMON_METRICS.alternative(branch) is (shape != "unrelated")


@pytest.mark.parametrize("shape", ["field", "named", "missing", "nonscope"])
def test_metric_body_prefers_explicit_body_then_language_named_body(shape):
    body = node("function_body")
    root = (
        node("function_definition", body=body)
        if shape == "field"
        else node(
            "function_definition" if shape != "nonscope" else "module",
            children=[body] if shape in {"named", "nonscope"} else [],
        )
    )
    assert get_metric_adapter("kotlin").metrics.body(root) is (
        body if shape in {"field", "named"} else root
    )


@pytest.mark.parametrize("kind", ["function_definition", "call", "identifier"])
def test_elixir_extra_scope_recognizes_declaration_calls(kind):
    expression = node(kind, target=node(value="defmodule"))
    assert get_metric_adapter("elixir").metrics.scope(expression) is (
        kind in {"function_definition", "call"}
    )


@pytest.mark.parametrize("operator", ["&&", "||", "and", "or", "+"])
def test_boolean_metrics_count_only_short_circuit_operators(operator):
    assert COMMON_METRICS.logical(
        node("binary_expression", children=[node(operator)])
    ) is (operator != "+")


@pytest.mark.parametrize("language", ["javascript", "jsx", "typescript", "tsx", "lua"])
def test_receiver_registry_exposes_dedicated_and_generic_language_policies(language):
    adapter = get_resolution_adapter(language)
    assert adapter.family == {
        "jsx": "javascript",
        "tsx": "javascript",
        "typescript": "javascript",
        "lua": "",
    }.get(language, language)


def test_receiver_inventory_covers_dedicated_and_generic_catalog_entries():
    inventory = receiver_coverage()
    assert {name: inventory[name]["status"] for name in ["python", "lua"]} == {
        "python": "dedicated",
        "lua": "generic",
    }
