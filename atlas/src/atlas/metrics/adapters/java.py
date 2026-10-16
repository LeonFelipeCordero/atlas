"""Java metric and resolution policies."""

import re

from ..receiver_syntax import java_bindings

from tree_sitter import Node

from .resolution import ResolutionAdapter
from .callable_selection import select_callable

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import count_parameters, parameter_node

from ..resolution_contract import SCOPES

from ...syntax import field, text


def parameter_count(node: Node) -> int | None:
    """Count Java inputs except explicit receivers; missing/error containers yield None."""
    parameters = parameter_node(node)
    if parameters is not None and parameters.type == "identifier":
        return 1
    return count_parameters(parameters, frozenset({"receiver_parameter"}))


def package(syntax) -> str:
    """Read the first Java/Kotlin package name, or an empty string when absent."""
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
    receiver_bindings = staticmethod(java_bindings)
    def import_path(self, source: str) -> str:
        """Extract a Java import name, preferring quoted paths and falling back to source."""
        match = re.search(r"\bimport\s+(?:static\s+)?([\w.]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "java"
    bare_instance_fields = True
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
    member_writes = {"assignment_expression", "update_expression"}
    single_parameter_functions = {"lambda_expression"}

    def select(self, identity, request, matches):
        """Return a sole viable JVM callable using conservative argument/type checks."""
        return select_callable(identity, request, matches)

    def call_target(self, node):
        """Extract constructors or two-part method references before shared call handling."""
        if node and node.type == "object_creation_expression":
            return field(node, "constructor", "type"), None
        if node and node.type == "method_reference" and len(node.named_children) == 2:
            return node.named_children[-1], node.named_children[0]
        return super().call_target(node)

    def binding(self, syntax, node, scope):
        """Add enhanced-for and catch bindings, keeping enhanced-for names loop-local."""
        if node.type == "enhanced_for_statement":
            return field(node, "name"), node
        if node.type == "catch_formal_parameter":
            return field(node, "name"), scope
        return super().binding(syntax, node, scope)

    def module_identity(self, file, symbol, syntax):
        """Prefix the symbol's language-qualified name with its declared package."""
        return ".".join(
            filter(None, [package(syntax), symbol.qualified_name.split("::")[-1]])
        )

    def same_package(self, modules, source, name):
        """Find declarations by source package and name, preserving duplicate matches."""
        identity = ".".join(
            filter(None, [package(modules.syntax[source.source.path]), name])
        )
        return modules.declared(source, identity)

    def import_name(self, source, path):
        """Read a full import name including static imports, or retain the supplied path."""
        match = re.search(r"\bimport\s+(?:static\s+)?([\w.]+)", source)
        return match[1] if match else path

    def import_key(self, ctx, request):
        """Return the unique imported declaration's key, or None if missing/ambiguous."""
        targets = ctx.modules.declared(
            request.file, self.import_name(request.source, request.path)
        )
        return targets[0].key if len(targets) == 1 else None

    def import_item(self, ctx, request):
        """Bind the import's final name to all matching declarations as a non-namespace."""
        path = self.import_name(request.source, request.path)
        return [(path.rsplit(".", 1)[-1], ctx.modules.declared(request.file, path), False)]

    def qualify_class(self, resolver, request, matches):
        """Resolve dotted type names by module identity; keep unqualified matches."""
        return resolver.modules.declared(request.file, request.name) if "." in request.name else matches

    def inheritance(self, resolver, request, matches):
        """Resolve dotted bases by module identity; otherwise use shared inheritance lookup."""
        return (
            resolver.modules.declared(request.file, request.name)
            if "." in request.name
            else super().inheritance(resolver, request, matches)
        )


METRICS = COMMON_METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
