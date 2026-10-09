"""Go extraction hooks."""

from tree_sitter import Node

from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
)


from .base import LanguageAdapter


from ...syntax import text

QUERY = "\n(func_literal) @definition.function\n"


CALLBACK_TYPES = frozenset({"func_literal"})


CALL_TYPES = frozenset({"call_expression"})


INHERITANCE = InheritancePolicy(frozenset())


def _binding(node: Node) -> str | None:
    """Pair a literal with its identifier by position in an assignment/spec."""
    values = node.parent
    if values is None or values.type != "expression_list" or values.parent is None:
        return None
    owner = values.parent
    if owner.type not in {"short_var_declaration", "assignment_statement", "var_spec"}:
        return None
    value_field = "value" if owner.type == "var_spec" else "right"
    if owner.child_by_field_name(value_field) != values:
        return None
    return _assigned_name(owner, values.named_children.index(node))


def _assigned_name(owner: Node, index: int) -> str | None:
    names = owner.children_by_field_name("name") if owner.type == "var_spec" else []
    left = owner.child_by_field_name("left")
    if left is not None:
        names = left.named_children
    if index >= len(names):
        return None
    name = names[index]
    return text(name) if name.type == "identifier" else None


def declaration(node: Node) -> DeclarationCarrier:
    if node.type == "func_literal":
        return callback_carrier(node, _binding(node))
    return named_carrier(node)


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
)
