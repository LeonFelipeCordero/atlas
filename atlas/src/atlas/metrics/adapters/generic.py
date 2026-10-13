"""Conservative, source-verified grammar hooks, not compiler/type inference.

Only the explicitly listed grammars opt in. Catalog membership does not imply
that an entry is a programming language, installed, or receiver-capable.
"""

from dataclasses import replace

from tree_sitter import Node

from ...syntax import field, text
from ..receiver_syntax import Declaration, declaration, type_name
from .resolution_policy import ResolutionAdapter

VERIFIED_HOOKS = {
    "csharp": ("annotated_parameters", "annotated_locals", "new_locals", "direct_new"),
    "php": ("annotated_parameters", "new_locals", "direct_new"),
    "ruby": ("constant_new_locals", "direct_constant_new"),
}
LIMITATIONS = {
    "csharp": "No overload selection, imports/namespaces, fields, target-typed new, or compiler semantics.",
    "php": "No namespace resolution, unions, dynamic class names, inheritance, or compiler semantics.",
    "ruby": "Conventional constant.new syntax only; no runtime construction guarantee, mixins, inheritance, or cross-file reopening analysis.",
}


def receiver_coverage(languages, dedicated) -> dict[str, dict[str, object]]:
    """JSON-serializable inventory for every supplied importer catalog entry."""
    return {
        language: {
            "status": "dedicated" if language in dedicated else "generic",
            "hooks": list(VERIFIED_HOOKS.get(language, ())),
            "verification": "physical_coffee_ast" if language in VERIFIED_HOOKS else "not_verified_here",
            "limitations": LIMITATIONS.get(language, "Dedicated policy" if language in dedicated else "Unresolved-only receiver fallback; no grammar hooks verified."),
        }
        for language in sorted(languages)
    }


def unwrapped(node: Node | None) -> Node | None:
    while node is not None and node.type == "parenthesized_expression" and len(node.named_children) == 1:
        node = node.named_children[0]
    return node


class GenericResolution(ResolutionAdapter):
    """No blanket name matching: unknown grammars retain no receiver bindings."""

    def __init__(self, language: str = ""):
        self.language = language
        if language == "csharp":
            self.assignments = {"assignment_expression"}
            self.declarations = {"variable_declarator"}
            self.member_nodes = {"member_access_expression": (("expression",), ("name",))}
            self.receiver_class_nodes = {"object_creation_expression"}
        elif language == "php":
            self.assignments = {"assignment_expression", "augmented_assignment_expression"}
            self.receiver_names = {"variable_name"}
            self.receiver_class_nodes = {"object_creation_expression"}
        elif language == "ruby":
            self.assignments = {"assignment", "operator_assignment"}
            self.scopes = self.scopes | {"class", "method", "singleton_method", "block", "do_block"}
            self.receiver_class_nodes = {"call"}
        self.constructors = self.receiver_class_nodes - {"call"}
        self.member_writes = self.assignments

    def call_target(self, node):
        node = unwrapped(node)
        if node is not None and node.type == "object_creation_expression" and self.language in {"csharp", "php"}:
            return self._construction_name(node), None
        if self.language == "ruby" and node is not None and self._ruby_new(node):
            return field(node, "receiver"), None
        callee, receiver = super().call_target(node)
        return callee, unwrapped(receiver)

    def _construction_name(self, node):
        if self.language == "csharp":
            return field(node, "type")
        return next((c for c in node.named_children if c.type == "name"), None)

    def normalized_call(self, call, callee, receiver):
        target = super().normalized_call(call, callee, receiver)
        # A construction expression is not a dotted lexical receiver path.
        if self.language == "ruby" and self._ruby_new(receiver):
            return replace(target, qualifier=None)
        return target

    @staticmethod
    def _ruby_new(node):
        receiver = field(node, "receiver") if node is not None else None
        return (node is not None and node.type == "call" and text(field(node, "method")) == "new"
                and receiver is not None and receiver.type == "constant")

    @staticmethod
    def receiver_bindings(syntax, node):
        adapter = syntax.adapter
        details = adapter._declaration(node)
        if adapter.language == "ruby" and node.type in {"method_parameters", "block_parameters"}:
            return [binding for name in adapter._ruby_parameter_names(node)
                    for binding in declaration(syntax, name, Declaration(name, None))]
        if details is None:
            return []
        if adapter.language == "csharp" and adapter._type_parameter_shadowed(node, details.annotation):
            details = replace(details, annotation=None, value=None)
        return declaration(syntax, node, details)

    @staticmethod
    def _ruby_parameter_names(node):
        if node.type == "identifier":
            return [node]
        if node.type in {"method_parameters", "block_parameters", "destructured_parameter"}:
            return [name for child in node.named_children for name in GenericResolution._ruby_parameter_names(child)]
        name = field(node, "name")
        return [name] if name is not None else []

    @staticmethod
    def _type_parameter_shadowed(node, name):
        parent = node.parent
        while parent is not None:
            if GenericResolution._scope_shadows_type(parent, name):
                return True
            parent = parent.parent
        return False

    @staticmethod
    def _scope_shadows_type(node, name):
        return any(GenericResolution._parameter_list_shadows_type(child, name) for child in node.named_children)

    @staticmethod
    def _parameter_list_shadows_type(node, name):
        return node.type == "type_parameter_list" and any(text(field(p, "name")) == name for p in node.named_children)

    def _declaration(self, node):
        if self.language == "csharp":
            return self._csharp_declaration(node)
        if self.language == "php":
            return self._php_declaration(node)
        if self.language == "ruby":
            return self._ruby_declaration(node)
        return None

    @staticmethod
    def _csharp_declaration(node):
        if node.type == "parameter":
            return Declaration(field(node, "name"), type_name(field(node, "type")))
        if node.type != "variable_declarator" or node.parent is None or node.parent.parent is None:
            return None
        # Only locals, never fields with different lifetime/static semantics.
        if node.parent.parent.type != "local_declaration_statement":
            return None
        name = field(node, "name")
        value = next((c for c in node.named_children if c != name), None)
        return Declaration(name, type_name(field(node.parent, "type")), unwrapped(value))

    @staticmethod
    def _php_declaration(node):
        if node.type == "simple_parameter":
            return Declaration(field(node, "name"), GenericResolution._php_parameter_type(node))
        if node.type == "assignment_expression":
            name = field(node, "left")
            if name is not None and name.type == "variable_name":
                return Declaration(name, None, unwrapped(field(node, "right")))
        return None

    @staticmethod
    def _php_parameter_type(node):
        annotation = field(node, "type")
        children = annotation.named_children if annotation is not None and annotation.type == "named_type" else []
        name = children[0] if len(children) == 1 and children[0].type == "name" else None
        return type_name(name)

    def _ruby_declaration(self, node):
        if node.type != "assignment":
            return None
        name = field(node, "left")
        if name is None or name.type != "identifier":
            return None
        value = field(node, "right")
        safe = self._ruby_new(value) and not self._ruby_conditional(node)
        return Declaration(name, None, value if safe else None)

    @staticmethod
    def _ruby_conditional(node):
        parent = node.parent
        while parent is not None and parent.type not in {"method", "singleton_method", "program"}:
            if parent.type in {"if", "unless", "case", "while", "until", "for", "rescue", "block", "do_block"}:
                return True
            parent = parent.parent
        return False

    def receiver_class_allowed(self, syntax, callee, member):
        if self.language == "csharp" and callee is not None and self._type_parameter_shadowed(callee, text(callee)):
            return False
        if self.language == "ruby" and (callee is None or callee.type != "constant"):
            return False
        return self.receiver_type_allowed(syntax, text(callee), member)

    def receiver_type_allowed(self, syntax, name, member):
        if self.language == "php" and any(n.type in {"namespace_definition", "namespace_use_declaration"} for n in syntax.nodes):
            return False
        if self.language == "ruby" and self._ruby_new_overridden(syntax):
            return False
        return super().receiver_type_allowed(syntax, name, member)

    @staticmethod
    def _ruby_new_overridden(syntax):
        # A visible override of new invalidates the syntactic construction hint.
        return any(n.type == "singleton_method" and text(field(n, "name")) == "new" for n in syntax.nodes)
