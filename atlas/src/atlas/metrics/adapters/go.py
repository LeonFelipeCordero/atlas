"""Go metric and resolution policies."""

import re

from itertools import chain

from tree_sitter import Node

from .resolution import ResolutionAdapter, top_symbols

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import parameter_children, parameter_node

from ..resolution_contract import SCOPES

from ...syntax import field


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node)
    if parameters is None or parameters.has_error:
        return None
    entries = parameter_children(parameters)
    if any(
        child.type not in {"parameter_declaration", "variadic_parameter_declaration"}
        for child in entries
    ):
        return None
    return sum(max(1, len(child.children_by_field_name("name"))) for child in entries)


class GoResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        return quoted_path(source) or source.strip()

    def import_item(self, ctx, request):
        source, path = request.source, request.path
        if re.match(r"\s*\.\s+['\"]", source):
            return []
        alias = re.match(r"\s*([A-Za-z_$][\w$]*)\s+['\"]", source)
        binding = (
            alias[1]
            if alias and alias[1] not in {"import", "require"}
            else path.replace(".", "/").rstrip("/").rsplit("/", 1)[-1]
        )
        targets = self.import_files(ctx, request)
        symbols = list(chain.from_iterable(top_symbols(target) for target in targets))
        return [(binding, symbols, True)] if binding else []

    family = "go"
    scopes = SCOPES | {"for_statement"}
    import_nodes = {"import_declaration"}
    assignments = {"assignment_statement", "short_var_declaration"}
    declarations = {"var_spec"}
    member_nodes = {"selector_expression": (("operand",), ("field",))}
    receiver_class_nodes = {"compound_literal_expression"}

    def binding(self, syntax, node, scope):
        if node.type == "range_clause":
            if not any(c.type == ":=" for c in node.children) and node.parent:
                scope = syntax.scope(node.parent)
            return field(node, "left"), scope
        return super().binding(syntax, node, scope)

    def call_target(self, node):
        if node and node.type == "compound_literal_expression":
            return field(node, "type"), None
        return super().call_target(node)


METRICS = COMMON_METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
