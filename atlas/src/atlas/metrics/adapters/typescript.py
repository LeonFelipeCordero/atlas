"""Typescript metric and resolution policies."""

from tree_sitter import Node

from . import javascript as script

from ...language_syntax import _property_callable
from .base import MetricAdapter
from .script_resolution import executable_implementation


def parameter_count(node: Node) -> int | None:
    callable_node = (
        _property_callable(node) if node.type == "property_signature" else node
    )
    return script.parameter_count(callable_node) if callable_node is not None else None


class TypeScriptResolution(script.JavaScriptResolution):
    def select(self, identity, request, matches):
        if len(matches) <= 1:
            return [s for s in matches if (node := identity.syntax[s.file_path].node(s.start_byte, s.end_byte))
                    is not None and node.type not in {"method_signature", "function_signature", "abstract_method_signature", "property_signature"}]
        if len({identity.syntax[s.file_path].static(s) for s in matches}) != 1:
            return []
        return executable_implementation(identity, matches, {"method_signature", "function_signature"})

METRICS = script.METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
