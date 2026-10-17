"""Kotlin metric and resolution policies."""

import re

from ..receiver_syntax import kotlin_bindings

from .resolution_paths import quoted_path

from dataclasses import replace

from tree_sitter import Node

from .java import JavaResolution

from .base import COMMON_METRICS, MetricAdapter

from .parameters import parameter_children, parameter_node

from ..resolution_contract import SCOPES


def alternative(node: Node) -> bool:
    """Recognize an else-if wrapped in Kotlin's alternative control-structure body."""
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
    """Count explicit inputs, treating a destructured input as one parameter.

    An explicit empty lambda header counts zero; implicit it and errors yield None.
    """
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


class KotlinResolution(JavaResolution):
    receiver_bindings = staticmethod(kotlin_bindings)
    def import_path(self, source: str) -> str:
        """Extract a Kotlin import path, preferring quoted text and falling back to source."""
        match = re.search(r"\bimport\s+([\w.]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "kotlin"
    scopes = SCOPES | {
        "lambda_literal",
        "secondary_constructor",
        "function_body",
        "control_structure_body",
        "for_statement",
    }
    import_nodes = {"import_header"}
    receiver_class_nodes = {"object_creation_expression", "call_expression"}
    assignments = {"assignment"}
    declarations = {"variable_declaration"}
    loop_bindings = frozenset()
    member_writes = {"assignment", "prefix_expression", "postfix_expression"}
    receiver_updates = {"prefix_expression", "postfix_expression"}

    def write_target(self, node):
        """Find write operands, rejecting prefix/postfix expressions other than ++/--."""
        if node.type in self.receiver_updates and not any(c.type in {"++", "--"} for c in node.children):
            return None
        return super().write_target(node)
    single_parameter_functions = {"lambda_expression"}

    def call_target(self, node):
        """Split navigation expressions into callee and receiver after Java target extraction."""
        callee, receiver = super().call_target(node)
        if callee and callee.type == "navigation_expression":
            receiver = callee.named_children[0]
            suffix = callee.named_children[-1]
            callee = suffix.named_children[-1] if suffix.named_children else suffix
        return callee, receiver

    def binding(self, syntax, node, scope):
        """Find property and loop variable targets, with loop variables scoped to the loop."""
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
        """Keep the normalized path rather than applying Java import-text parsing."""
        return path

    def import_item(self, ctx, request):
        """Bind an explicit alias or final path name to module-qualified declarations."""
        file, source, path = request.file, request.source, request.path
        alias = re.search(r"\bas\s*:?\s*([\w]+)", source)
        return [
            (
                alias[1] if alias else path.rsplit(".", 1)[-1],
                ctx.modules.declared(file, path),
                False,
            )
        ]

    def static_member(self, parent):
        """Allow module and singleton-object members without a static modifier."""
        return parent.kind in {"module", "object"}


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
