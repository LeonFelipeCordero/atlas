"""Typescript metric and resolution policies."""

from tree_sitter import Node

from . import javascript as script

from ...language_syntax import _property_callable
from .base import MetricAdapter


def parameter_count(node: Node) -> int | None:
    callable_node = (
        _property_callable(node) if node.type == "property_signature" else node
    )
    return script.parameter_count(callable_node) if callable_node is not None else None


TypeScriptResolution = script.JavaScriptResolution
METRICS = script.METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
