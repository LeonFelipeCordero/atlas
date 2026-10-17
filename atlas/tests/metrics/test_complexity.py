"""Normalized syntax facts, not language parsers, drive these unit tests."""

import pytest

from atlas.domain.models import Complexity
from atlas.metrics.adapters.base import MetricPolicy
from atlas.metrics.complexity import calculate_complexity
from tests.metrics.metric_core_support import SyntaxNode, as_node, syntax


@pytest.mark.parametrize(("root", "expected"), [
    (syntax("block"), Complexity(1, 0, 0, 1, 0)),
    (syntax("if_statement"), Complexity(2, 0, 0, 2, 1)),
    (syntax("if_statement", syntax("if_statement", syntax("if_statement"))),
     Complexity(4, 1, 0, 5, 3)),
    (syntax("while_statement", syntax("for_statement", syntax("while_statement"))),
     Complexity(4, 1, 2, 7, 3)),
    (syntax("block", syntax("while_statement"), syntax("for_statement")),
     Complexity(3, 0, 0, 3, 1)),
    (syntax("if_statement", syntax("elif_clause", syntax("if_statement"))),
     Complexity(4, 0, 0, 4, 2)),
    (syntax("elif_clause"), Complexity(2, 0, 0, 2, 1)),
])
def test_decision_depth_loop_penalties_and_alternatives(root: SyntaxNode, expected: Complexity) -> None:
    # Given normalized decision facts, when traversed, then all five metrics agree.
    assert calculate_complexity(as_node(root)) == expected


def test_logical_operators_count_without_increasing_decision_depth() -> None:
    logical = syntax("boolean_operator")
    logical.children = [syntax("and"), syntax("or")]
    root = syntax("if_statement", logical, syntax("boolean_operator"))

    result = calculate_complexity(as_node(root))

    assert result == Complexity(3, 0, 0, 3, 1)


def test_callable_body_is_selected_and_nested_scopes_are_excluded() -> None:
    body = syntax("block", syntax("if_statement"),
                  syntax("function_definition", syntax("while_statement")),
                  syntax("class_definition", syntax("if_statement")))
    root = syntax("function_definition", syntax("if_statement"), body)
    root.body = body

    result = calculate_complexity(as_node(root))

    assert result == Complexity(2, 0, 0, 2, 1)


def test_scope_root_without_body_is_still_traversed() -> None:
    root = syntax("function_definition", syntax("if_statement"))

    result = calculate_complexity(as_node(root))

    assert result == Complexity(2, 0, 0, 2, 1)


def test_adapter_policy_controls_decisions_loops_and_scope() -> None:
    policy = MetricPolicy(decisions=frozenset({"branch", "repeat"}),
                          loops=frozenset({"repeat"}), scopes=frozenset({"hidden"}))
    root = syntax("branch", syntax("repeat", syntax("repeat")),
                  syntax("hidden", syntax("branch")), syntax("if_statement"))

    result = calculate_complexity(as_node(root), policy)

    assert result == Complexity(4, 1, 1, 6, 3)
