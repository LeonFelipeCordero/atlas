"""Go extraction, metrics and resolution policies."""

from tree_sitter import Node
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
    text,
    field,
)
from .resolution import ResolutionAdapter
from ..extraction.resolution_syntax import SCOPES

QUERY = "\n(func_literal) @definition.function\n"
CALLBACK_TYPES = frozenset({"func_literal"})
CALL_TYPES = frozenset({"call_expression"})
INHERITANCE = InheritancePolicy(frozenset())


def _binding(node: Node) -> str | None:
    """Pair a literal with its identifier by position in an assignment/spec."""
    values = node.parent
    if values is None or values.type != "expression_list" or values.parent is None:
        return None
    owner = values.parent
    if owner.type not in {"short_var_declaration", "assignment_statement", "var_spec"}:
        return None
    value_field = "value" if owner.type == "var_spec" else "right"
    if owner.child_by_field_name(value_field) != values:
        return None
    return _assigned_name(owner, values.named_children.index(node))


def _assigned_name(owner: Node, index: int) -> str | None:
    names = owner.children_by_field_name("name") if owner.type == "var_spec" else []
    left = owner.child_by_field_name("left")
    if left is not None:
        names = left.named_children
    if index >= len(names):
        return None
    name = names[index]
    return text(name) if name.type == "identifier" else None


def declaration(node: Node) -> DeclarationCarrier:
    if node.type == "func_literal":
        return callback_carrier(node, _binding(node))
    return named_carrier(node)


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


class GoResolution(ResolutionAdapter):
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
