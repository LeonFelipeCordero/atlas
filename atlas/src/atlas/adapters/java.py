"""Java extraction, metrics and resolution policies."""

import re
from tree_sitter import Node
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
    modifier_metadata,
    field,
    text,
)
from .resolution import ResolutionAdapter
from ..extraction.resolution_syntax import SCOPES

QUERY = """
(lambda_expression) @definition.function
(package_declaration (_) @name) @definition.module
"""
CALLBACK_TYPES = frozenset({"lambda_expression"})
CALL_TYPES = frozenset(
    {"method_invocation", "object_creation_expression", "method_reference"}
)
INHERITANCE = InheritancePolicy(
    frozenset({"superclass", "super_interfaces", "extends_interfaces"}),
    complete_header=True,
)


def declaration(node: Node) -> DeclarationCarrier:
    if node.type in {"constructor_declaration", "compact_constructor_declaration"}:
        return DeclarationCarrier(node, kind="constructor")
    if node.type == "lambda_expression":
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(node, frozenset({"public", "private", "protected"}))


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

    def import_key(self, ctx, file, source, position):
        from .resolution import import_path

        targets = ctx.modules.declared(
            file, self.import_name(source, import_path(source))
        )
        return targets[0].key if len(targets) == 1 else None

    def import_item(self, ctx, file, source, path, position):
        path = self.import_name(source, path)
        return [(path.rsplit(".", 1)[-1], ctx.modules.declared(file, path), False)]

    def qualify_class(self, resolver, file, name, matches):
        return resolver.modules.declared(file, name) if "." in name else matches

    def inheritance(self, resolver, file, name, call, owner, matches):
        return (
            resolver.modules.declared(file, name)
            if "." in name
            else super().inheritance(resolver, file, name, call, owner, matches)
        )
