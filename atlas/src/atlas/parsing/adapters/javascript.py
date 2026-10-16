"""Javascript extraction hooks."""

from collections.abc import Iterator


from typing import Literal

from tree_sitter import Node


from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    normalize_call as shared_normalize_call,
    InheritancePolicy,
    modifier_metadata,
)


from .base import LanguageAdapter


from ...syntax import text, walk

SCRIPT_CALLBACKS = frozenset(
    {"arrow_function", "function_expression", "generator_function"}
)


SCRIPT_QUERY = """
[(arrow_function) (function_expression) (generator_function)] @definition.function
"""


CALL_TYPES = frozenset({"call_expression", "new_expression"})


INHERITANCE = InheritancePolicy(
    frozenset({"extends_clause", "extends_type_clause", "implements_clause"}),
    complete_header=True,
    heritage_clause="class_heritage",
)


JSX_TAGS = frozenset({"jsx_opening_element", "jsx_self_closing_element"})


def _component(node: Node) -> bool:
    if node.type == "member_expression":
        return True  # Namespaces may start lowercase: <cards.CoffeeCard />.
    name = text(node)
    return (
        node.type == "identifier"
        and bool(name)
        and not ("a" <= name[0] <= "z" or "-" in name)
    )


def is_jsx_site(node: Node) -> bool:
    """Test whether the node names an opening or self-closing JSX tag."""
    parent = node.parent
    return bool(
        parent is not None
        and parent.type in JSX_TAGS
        and parent.child_by_field_name("name") == node
    )


def call_sites(root: Node) -> Iterator[CallSite]:
    """Yield calls, constructors, and component JSX tags, excluding native tags."""
    for node in walk(root):
        if node.type in CALL_TYPES or is_jsx_site(node) and _component(node):
            yield node, 0, False, ()


def normalize_call(site: CallSite) -> CallTarget:
    """Split JSX names into member/qualifier; use shared extraction for calls."""
    node = site[0]
    if is_jsx_site(node):
        name = text(node)
        qualifier, separator, member = name.rpartition(".")
        return (member, False, qualifier) if separator else (name, True, None)
    return shared_normalize_call(site)


def call_relationship(site: CallSite) -> Literal["CALLS", "REFERENCES"]:
    """Classify JSX component usage as a reference and other sites as calls."""
    return "REFERENCES" if is_jsx_site(site[0]) else "CALLS"


def metadata(node: Node) -> tuple[str | None, list[str]]:
    """Return explicit visibility and annotations without inferring defaults."""
    return modifier_metadata(node, frozenset({"public", "private", "protected"}))


def unparenthesized(node: Node) -> Node:
    """Only a single expression in parentheses is transparent, not a sequence."""
    while node.type == "parenthesized_expression":
        expressions = _expressions(node)
        if len(expressions) != 1:
            break
        node = expressions[0]
    return node


def _expressions(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type != "comment"]


def script_declaration(node: Node) -> DeclarationCarrier:
    """Use callback values as carriers, naming them from supported bindings.

    Unwrap single-expression parentheses; keep other declarations as named nodes.
    """
    expression = unparenthesized(node)
    if expression.type in SCRIPT_CALLBACKS:
        node = expression
    value_field = "right" if node.type == "assignment_expression" else "value"
    value = node.child_by_field_name(value_field)
    value = unparenthesized(value) if value is not None else None
    if node.type in {"variable_declarator", "assignment_expression", "pair"}:
        if value is not None and value.type in SCRIPT_CALLBACKS:
            node = value
    if node.type in SCRIPT_CALLBACKS:
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


ADAPTER = LanguageAdapter(
    declaration_query=SCRIPT_QUERY,
    callback_types=SCRIPT_CALLBACKS,
    normalize_declaration=script_declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
    normalize_call=normalize_call,
    metadata=metadata,
    call_relationship=call_relationship,
)
