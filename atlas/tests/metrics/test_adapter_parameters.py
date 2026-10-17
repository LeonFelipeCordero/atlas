"""Arity counts represent declared inputs, not receivers or grammar tokens."""

import pytest

from atlas.metrics.adapters import (
    elixir,
    go,
    java,
    javascript,
    kotlin,
    python,
    rust,
    typescript,
)
from atlas.metrics.adapters.base import COMMON_METRICS
from tests.metrics.adapter_support import node


@pytest.mark.parametrize(
    "counter",
    [
        python.parameter_count,
        java.parameter_count,
        javascript.parameter_count,
        typescript.parameter_count,
        go.parameter_count,
        rust.parameter_count,
        kotlin.parameter_count,
    ],
)
def test_missing_and_malformed_parameter_lists_remain_unknown(counter):
    assert counter(node("function_declaration")) is None
    assert (
        counter(node("function_declaration", parameters=node("parameters", error=True)))
        is None
    )
    assert counter(node("function_declaration", parameters=node("parameters"))) == 0


@pytest.mark.parametrize(
    ("counter", "kinds", "expected"),
    [
        (
            python.parameter_count,
            [
                "identifier",
                "positional_separator",
                "keyword_separator",
                "default_parameter",
                "comment",
            ],
            2,
        ),
        (
            java.parameter_count,
            [
                "receiver_parameter",
                "formal_parameter",
                "spread_parameter",
                "line_comment",
            ],
            2,
        ),
        (
            rust.parameter_count,
            ["self_parameter", "parameter", "attribute_item", "block_comment"],
            1,
        ),
        (
            kotlin.parameter_count,
            [
                "parameter",
                "variable_declaration",
                "multi_variable_declaration",
                "line_comment",
            ],
            3,
        ),
        (
            javascript.parameter_count,
            ["this", "identifier", "rest_pattern", "comment"],
            2,
        ),
        (
            typescript.parameter_count,
            ["this", "identifier", "rest_pattern", "comment"],
            2,
        ),
    ],
)
def test_language_parameter_count_excludes_receivers_separators_and_comments(
    counter, kinds, expected
):
    declaration = node(
        "function_declaration",
        parameters=node("parameters", children=[node(kind) for kind in kinds]),
    )
    assert counter(declaration) == expected


@pytest.mark.parametrize("static", [False, True])
def test_python_method_receiver_is_removed_only_for_instance_methods(static):
    method = node(
        "function_definition",
        parameters=node(
            "parameters", children=[node(value="self"), node(value="value")]
        ),
    )
    owner = (
        node(
            "decorated_definition",
            children=[node("decorator", children=[node(value="staticmethod")]), method],
        )
        if static
        else method
    )
    node("class_definition", body=node("block", children=[owner]))
    assert python.parameter_count(method) == (2 if static else 1)


def test_python_free_function_keeps_self_named_input_and_empty_lambda_has_zero():
    declaration = node(
        "function_definition",
        parameters=node("parameters", children=[node(value="self")]),
    )
    assert python.parameter_count(declaration) == 1
    assert python.parameter_count(node("lambda")) == 0


def test_go_grouped_names_count_each_input_and_unnamed_variadic_counts_once():
    parameters = node(
        "parameter_list",
        children=[
            node("parameter_declaration", name=[node(value="x"), node(value="y")]),
            node("variadic_parameter_declaration"),
            node("comment"),
        ],
    )
    assert go.parameter_count(node("function_declaration", parameters=parameters)) == 3
    parameters.named_children.append(node("ERROR"))
    assert (
        go.parameter_count(node("function_declaration", parameters=parameters)) is None
    )


def test_rust_typed_self_pattern_does_not_add_an_input():
    parameters = node(
        "parameters",
        children=[node("parameter", pattern=node("self")), node("parameter")],
    )
    assert rust.parameter_count(node("function_item", parameters=parameters)) == 1


def test_script_this_annotation_is_not_a_runtime_parameter():
    parameters = node(
        "formal_parameters",
        children=[
            node("required_parameter", pattern=node("this")),
            node("required_parameter"),
        ],
    )
    assert (
        javascript.parameter_count(node("function_declaration", parameters=parameters))
        == 1
    )


@pytest.mark.parametrize("counter", [javascript.parameter_count, java.parameter_count])
def test_single_identifier_lambda_parameter_counts_once(counter):
    assert counter(node("lambda_expression", parameter=node(value="input"))) == 1


def test_kotlin_lambda_arrow_distinguishes_zero_inputs_from_implicit_it():
    assert kotlin.parameter_count(node("lambda_literal", children=[node("->")])) == 0
    assert kotlin.parameter_count(node("lambda_literal")) is None


@pytest.mark.parametrize(
    ("counts", "expected"), [([1, 1], 1), ([0, 0], 0), ([1, 2], None), ([], None)]
)
def test_elixir_anonymous_function_arity_requires_consistent_clauses(counts, expected):
    clauses = [
        node(
            "stab_clause",
            left=node("arguments", children=[node() for _ in range(count)]),
        )
        for count in counts
    ]
    assert (
        elixir.parameter_count(node("anonymous_function", children=clauses)) == expected
    )


@pytest.mark.parametrize(
    ("kind", "fallback", "expected"),
    [
        ("switch_case", "default", False),
        ("when_entry", "else", False),
        ("switch_case", "case", True),
        ("if_statement", "default", True),
    ],
)
def test_default_arms_do_not_add_decisions(kind, fallback, expected):
    assert COMMON_METRICS.decision(node(kind, children=[node(fallback)])) is expected


@pytest.mark.parametrize(("value", "expected"), [("_", False), ("Some(value)", True)])
def test_rust_wildcard_arm_is_not_a_decision(value, expected):
    assert (
        rust.METRICS.decision(node("match_arm", pattern=node(value=value))) is expected
    )


def test_python_capture_case_is_irrefutable_but_literal_case_is_a_decision():
    capture = node(
        "case_clause",
        children=[
            node(
                "case_pattern",
                children=[node("dotted_name", children=[node(value="captured")])],
            )
        ],
    )
    literal = node(
        "case_clause", children=[node("case_pattern", children=[node("integer", "1")])]
    )
    assert python.METRICS.decision(capture) is False
    assert python.METRICS.decision(literal) is True
