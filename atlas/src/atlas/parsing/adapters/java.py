"""Java extraction hooks."""

from tree_sitter import Node

from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
    modifier_metadata,
)


from .base import LanguageAdapter


QUERY = """
(lambda_expression) @definition.function
(package_declaration (_) @name) @definition.module
"""


CALLBACK_TYPES = frozenset({"lambda_expression"})


CALL_TYPES = frozenset(
    {"method_invocation", "object_creation_expression", "method_reference"}
)


INHERITANCE = InheritancePolicy(
    frozenset({"superclass", "super_interfaces", "extends_interfaces"}),
    complete_header=True,
)


def declaration(node: Node) -> DeclarationCarrier:
    if node.type in {"constructor_declaration", "compact_constructor_declaration"}:
        return DeclarationCarrier(node, kind="constructor")
    if node.type == "lambda_expression":
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(node, frozenset({"public", "private", "protected"}))


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
    metadata=metadata,
)
