"""Typescript extraction, metrics and resolution policies."""

from dataclasses import replace

from tree_sitter import Node
from . import javascript as script
from ..extraction.syntax import DeclarationCarrier, field, text

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
    if node.type != "property_signature":
        return script.script_declaration(node)
    if _property_callable(node) is None:
        return None
    name = node.child_by_field_name("name")
    return DeclarationCarrier(node, text(name) if name is not None else None, "method")


def _property_callable(node: Node) -> Node | None:
    annotation = field(node, "type")
    while annotation is not None and annotation.type in {
        "type_annotation",
        "parenthesized_type",
    }:
        annotation = next(iter(annotation.named_children), None)
    if annotation is None or annotation.type != "function_type":
        return None
    return annotation


def parameter_count(node: Node) -> int | None:
    callable_node = _property_callable(node) if node.type == "property_signature" else node
    return script.parameter_count(callable_node) if callable_node is not None else None


ADAPTER = replace(
    script.ADAPTER,
    declaration_query=QUERY,
    normalize_declaration=declaration,
    parameter_count=parameter_count,
)
