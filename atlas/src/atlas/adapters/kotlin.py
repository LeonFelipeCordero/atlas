"""Kotlin extraction, metrics and resolution policies."""

import re
from .resolution_paths import quoted_path
from dataclasses import replace
from tree_sitter import Node
from .java import JavaResolution
from .base import COMMON_METRICS, LanguageAdapter
from .parameters import parameter_children, parameter_node
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    call_target,
    call_member,
    call_sites as shared_call_sites,
    InheritancePolicy,
    modifier_metadata,
    text,
)
from ..extraction.resolution_syntax import SCOPES

QUERY = """
(package_header (identifier) @name) @definition.module
(companion_object) @definition.class
[(lambda_literal) (anonymous_function)] @definition.function
"""
CALLBACK_TYPES = frozenset({"lambda_literal", "anonymous_function"})
CALL_TYPES = frozenset({"call_expression", "callable_reference"})
IMPORT_NODE = "import_header"


def _base_name(node: Node) -> str | None:
    if node.type != "user_type":
        return None
    return (
        ".".join(
            text(child)
            for child in node.named_children
            if child.type == "type_identifier"
        )
        or None
    )


INHERITANCE = InheritancePolicy(
    frozenset({"delegation_specifier"}), complete_header=True, base_name=_base_name
)


def declaration(node: Node) -> DeclarationCarrier:
    if node.type in {"lambda_literal", "anonymous_function"}:
        return callback_carrier(node, callback_binding(node))
    if node.type == "function_declaration":
        return DeclarationCarrier(node, _identifier_name(node, "simple_identifier"))
    return _type_declaration(node)


def _identifier_name(node: Node, kind: str) -> str | None:
    name = next((child for child in node.named_children if child.type == kind), None)
    return text(name) if name is not None else None


def _type_declaration(node: Node) -> DeclarationCarrier:
    carrier = named_carrier(node)
    if node.type == "companion_object" and carrier.name is None:
        name = _identifier_name(node, "type_identifier")
        return DeclarationCarrier(node, name if name is not None else "Companion")
    if node.type == "class_declaration" and any(
        child.type == "interface" for child in node.children
    ):
        return DeclarationCarrier(node, carrier.name, "interface")
    return carrier


def _member(target: Node) -> str:
    if target.type != "navigation_expression":
        return call_member(target)
    suffix = next(
        (
            child
            for child in reversed(target.named_children)
            if child.type == "navigation_suffix"
        ),
        None,
    )
    member = next(iter(suffix.named_children), None) if suffix else None
    return text(member or target).strip()


def normalize_call(site: CallSite) -> CallTarget:
    return call_target(site[0], _member)


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(
        node, frozenset({"public", "private", "protected", "internal"})
    )


def alternative(node: Node) -> bool:
    parent = node.parent
    owner = parent.parent if parent is not None else None
    return bool(
        node.type == "if_expression"
        and parent is not None
        and parent.type == "control_structure_body"
        and owner is not None
        and owner.type == "if_expression"
        and owner.child_by_field_name("alternative") == parent
    )


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node, "function_value_parameters", "lambda_parameters")
    if parameters is None:
        # An implicit lambda input (it) cannot be inferred without type resolution.
        return (
            0
            if node.type == "lambda_literal"
            and any(child.type == "->" for child in node.children)
            else None
        )
    if parameters.has_error:
        return None
    entries = parameter_children(parameters)
    return sum(
        child.type
        in {"parameter", "variable_declaration", "multi_variable_declaration"}
        for child in entries
    )


METRICS = replace(
    COMMON_METRICS, extra_alternative=alternative, body_node="function_body"
)
ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    import_node=IMPORT_NODE,
    inheritance_policy=INHERITANCE,
    normalize_call=normalize_call,
    metadata=metadata,
    metrics=METRICS,
    parameter_count=parameter_count,
)


class KotlinResolution(JavaResolution):
    def import_path(self, source: str) -> str:
        match = re.search(r"\bimport\s+([\w.]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "kotlin"
    scopes = SCOPES | {
        "lambda_literal",
        "function_body",
        "control_structure_body",
        "for_statement",
    }
    import_nodes = {"import_header"}
    receiver_class_nodes = {"object_creation_expression", "call_expression"}
    assignments = {"assignment"}
    declarations = {"variable_declaration"}
    loop_bindings = frozenset()
    member_writes = {"assignment"}
    single_parameter_functions = {"lambda_expression"}

    def call_target(self, node):
        callee, receiver = super().call_target(node)
        if callee and callee.type == "navigation_expression":
            receiver = callee.named_children[0]
            suffix = callee.named_children[-1]
            callee = suffix.named_children[-1] if suffix.named_children else suffix
        return callee, receiver

    def binding(self, syntax, node, scope):
        if node.type == "property_declaration":
            return next(
                (c for c in node.named_children if c.type == "variable_declaration"),
                None,
            ), scope
        if node.type == "for_statement":
            target = next(
                (
                    c
                    for c in node.named_children
                    if c.type in {"variable_declaration", "multi_variable_declaration"}
                ),
                None,
            )
            return target, node
        return super().binding(syntax, node, scope)

    def import_name(self, source, path):
        return path

    def import_item(self, ctx, file, source, path, position):
        alias = re.search(r"\bas\s*:?\s*([\w]+)", source)
        return [
            (
                alias[1] if alias else path.rsplit(".", 1)[-1],
                ctx.modules.declared(file, path),
                False,
            )
        ]

    def static_member(self, parent):
        return parent.kind in {"module", "object"}
