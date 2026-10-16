"""Python extraction hooks."""

from tree_sitter import Node


from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
)


from .base import LanguageAdapter

from ...syntax import text

QUERY = "\n(lambda) @definition.function\n"


CALLBACK_TYPES = frozenset({"lambda"})


CALL_TYPES = frozenset({"call"})


INHERITANCE = InheritancePolicy(frozenset(), superclass_field="superclasses")


def declaration(node: Node) -> DeclarationCarrier:
    """Unwrap decorated definitions and retain decorator text on their carriers.

    Mark lambdas as function carriers, using a supported binding when available.
    """
    if node.type == "decorated_definition":
        node = node.child_by_field_name("definition") or node
    if node.type == "lambda":
        return callback_carrier(node, callback_binding(node))
    carrier = named_carrier(node)
    if node.parent is not None and node.parent.type == "decorated_definition":
        decorators = tuple(
            text(child)
            for child in node.parent.named_children
            if child.type == "decorator"
        )
        return DeclarationCarrier(node, carrier.name, decorators=decorators)
    return carrier


def call_sites(root: Node):
    """Iterate Python call nodes with original-source coordinates."""
    return shared_call_sites(root, CALL_TYPES)


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
)
