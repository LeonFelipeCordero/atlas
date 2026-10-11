"""Go metric and resolution policies."""

import re

from itertools import chain

from tree_sitter import Node

from .resolution import ResolutionAdapter, top_symbols

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import parameter_children, parameter_node

from ..resolution_contract import SCOPES

from ...syntax import field, text
from ..receiver_syntax import go_bindings, type_name


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
    receiver_bindings = staticmethod(go_bindings)

    def instance_members(self, resolver, parent, name):
        symbols = self._package_symbols(resolver, resolver.files[parent.file_path])
        return [s for s in symbols if self._receiver_method(resolver, s, parent, name)]

    def _package_symbols(self, ctx, source):
        return chain.from_iterable(f.symbols for f in self._package_files(ctx, source))

    def _receiver_method(self, resolver, symbol, parent, name):
        if symbol.kind != "method" or symbol.name != name:
            return False
        node = resolver.syntax[symbol.file_path].node(symbol.start_byte, symbol.end_byte)
        receiver = field(node, "receiver") if node else None
        parameter = receiver.named_children[0] if receiver and receiver.named_children else None
        return bool(parameter and type_name(field(parameter, "type")) == parent.name)

    def _package_files(self, resolver, source):
        package = self._package(resolver, source)
        files = (syntax.file for syntax in resolver.syntax.values())
        return [f for f in files if f.source.language == "go" and self._package(resolver, f) == package]

    def _package(self, resolver, file):
        syntax = resolver.syntax[file.source.path]
        return (file.source.path.rpartition("/")[0], next((text(n) for n in syntax.nodes if n.type == "package_clause"), ""))

    def same_package(self, modules, source, name):
        return [s for file in self._package_files(modules, source)
                for s in file.symbols if s.name == name and s.kind == "type"]
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
    receiver_updates = {"inc_statement", "dec_statement"}
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
