"""Typescript extraction hooks."""

from dataclasses import replace

from tree_sitter import Node

from . import javascript as script

from ..syntax import DeclarationCarrier
from ...language_syntax import _property_callable
from ...syntax import text

QUERY = (
    """
[(function_declaration) (generator_function_declaration)] @definition.function
[(class_declaration) (class)] @definition.class
(method_definition) @definition.method
(interface_body (property_signature name: (_) @name) @definition.method)
"""
    + script.SCRIPT_QUERY
)


def declaration(node: Node) -> DeclarationCarrier | None:
    """Mark callable property signatures as methods; skip non-callable properties.

    Delegate other nodes to JavaScript declaration normalization.
    """
    if node.type != "property_signature":
        return script.script_declaration(node)
    if _property_callable(node) is None:
        return None
    name = node.child_by_field_name("name")
    return DeclarationCarrier(node, text(name) if name is not None else None, "method")


ADAPTER = replace(
    script.ADAPTER,
    declaration_query=QUERY,
    normalize_declaration=declaration,
)
