"""Java metric and resolution policies."""

import re

from tree_sitter import Node

from .resolution import ResolutionAdapter

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import count_parameters, parameter_node

from ..resolution_contract import SCOPES

from ...syntax import field, text


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node)
    if parameters is not None and parameters.type == "identifier":
        return 1
    return count_parameters(parameters, frozenset({"receiver_parameter"}))


def package(syntax) -> str:
    node = next(
        (
            n
            for n in syntax.nodes
            if n.type in {"package_declaration", "package_header"}
        ),
        None,
    )
    match = re.search(r"\bpackage\s+([\w.]+)", text(node))
    return match[1] if match else ""


class JavaResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        match = re.search(r"\bimport\s+(?:static\s+)?([\w.]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "java"
    scopes = SCOPES | {"for_statement", "enhanced_for_statement", "catch_clause"}
    import_nodes = {"import_declaration"}
    self_qualifiers = {"this"}
    constructors = {"object_creation_expression"}
    receiver_class_nodes = {"object_creation_expression"}
    receiver_names = {"this"}
    assignments = {"assignment_expression"}
    declarations = {"variable_declarator", "init_declarator"}
    loop_bindings = {"for_statement"}
    static_nodes = {"static"}
    static_containers = {"modifiers"}
    member_writes = {"assignment_expression"}
    single_parameter_functions = {"lambda_expression"}

    def call_target(self, node):
        if node and node.type == "object_creation_expression":
            return field(node, "constructor", "type"), None
        if node and node.type == "method_reference" and len(node.named_children) == 2:
            return node.named_children[-1], node.named_children[0]
        return super().call_target(node)

    def binding(self, syntax, node, scope):
        if node.type == "enhanced_for_statement":
            return field(node, "name"), node
        if node.type == "catch_formal_parameter":
            return field(node, "name"), scope
        return super().binding(syntax, node, scope)

    def module_identity(self, file, symbol, syntax):
        return ".".join(
            filter(None, [package(syntax), symbol.qualified_name.split("::")[-1]])
        )

    def same_package(self, modules, source, name):
        identity = ".".join(
            filter(None, [package(modules.syntax[source.source.path]), name])
        )
        return modules.declared(source, identity)

    def import_name(self, source, path):
        match = re.search(r"\bimport\s+(?:static\s+)?([\w.]+)", source)
        return match[1] if match else path

    def import_key(self, ctx, request):
        targets = ctx.modules.declared(
            request.file, self.import_name(request.source, request.path)
        )
        return targets[0].key if len(targets) == 1 else None

    def import_item(self, ctx, request):
        path = self.import_name(request.source, request.path)
        return [(path.rsplit(".", 1)[-1], ctx.modules.declared(request.file, path), False)]

    def qualify_class(self, resolver, request, matches):
        return resolver.modules.declared(request.file, request.name) if "." in request.name else matches

    def inheritance(self, resolver, request, matches):
        return (
            resolver.modules.declared(request.file, request.name)
            if "." in request.name
            else super().inheritance(resolver, request, matches)
        )


METRICS = COMMON_METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
