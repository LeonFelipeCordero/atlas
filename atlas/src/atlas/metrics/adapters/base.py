"""Complexity and parameter-count contracts."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Mapping

from tree_sitter import Node

LOOPS = frozenset(
    {
        "for_statement",
        "for_in_statement",
        "enhanced_for_statement",
        "foreach_statement",
        "for_each_statement",
        "while_statement",
        "do_statement",
        "do_while_statement",
        "for_expression",
        "while_expression",
        "loop_expression",
        "for_in_clause",
        "for_range_loop",
    }
)
DECISIONS = LOOPS | {
    "if_statement",
    "if_expression",
    "elif_clause",
    "if_clause",
    "conditional_expression",
    "ternary_expression",
    "catch_clause",
    "except_clause",
    "switch_case",
    "case_statement",
    "switch_label",
    "expression_case",
    "type_case",
    "match_arm",
    "when_entry",
    "case_clause",
}
SCOPES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "arrow_function",
        "method_definition",
        "method_declaration",
        "constructor_declaration",
        "function_item",
        "lambda",
        "lambda_expression",
        "lambda_literal",
        "anonymous_function",
        "func_literal",
        "closure_expression",
        "class_definition",
        "class_declaration",
        "class",
        "object_declaration",
        "class_specifier",
    }
)
BOOLEANS = frozenset(
    {
        "binary_expression",
        "boolean_operator",
        "binary_operator",
        "infix_expression",
        "conjunction_expression",
        "disjunction_expression",
    }
)


def never(node: Node) -> bool:
    return False


def alternative(node: Node) -> bool:
    if node.type == "elif_clause":
        return True
    if node.type not in {"if_statement", "if_expression"}:
        return False
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "else_clause":
        return _conditional_parent(parent.parent)
    return (
        _conditional_parent(parent)
        and parent.child_by_field_name("alternative") == node
    )


def _conditional_parent(parent: Node | None) -> bool:
    return parent is not None and parent.type in {"if_statement", "if_expression"}


@dataclass(frozen=True)
class MetricPolicy:
    decisions: frozenset[str] = DECISIONS
    loops: frozenset[str] = LOOPS
    scopes: frozenset[str] = SCOPES
    booleans: frozenset[str] = BOOLEANS
    decision_overrides: Mapping[str, Callable[[Node], bool]] = field(
        default_factory=dict
    )
    extra_scope: Callable[[Node], bool] = never
    extra_alternative: Callable[[Node], bool] = never
    body_node: str | None = None

    def body(self, root: Node) -> Node:
        if root.type not in self.scopes:
            return root
        body = root.child_by_field_name("body")
        return body or next(
            (child for child in root.named_children if child.type == self.body_node),
            root,
        )

    def scope(self, node: Node) -> bool:
        return node.type in self.scopes or self.extra_scope(node)

    def decision(self, node: Node) -> bool:
        override = self.decision_overrides.get(node.type)
        if override is not None:
            return override(node)
        if node.type not in self.decisions:
            return False
        if node.type in {"switch_case", "case_statement", "switch_label", "when_entry"}:
            return not any(child.type in {"default", "else"} for child in node.children)
        return True

    def logical(self, node: Node) -> bool:
        return node.type in self.booleans and any(
            child.type in {"&&", "||", "and", "or"} for child in node.children
        )

    def alternative(self, node: Node) -> bool:
        return alternative(node) or self.extra_alternative(node)


COMMON_METRICS = MetricPolicy()
DEFAULT_METRICS = COMMON_METRICS


@dataclass(frozen=True)
class MetricAdapter:
    metrics: MetricPolicy = DEFAULT_METRICS
    parameter_count: Callable[[Node], int | None] = lambda node: None
