"""Go extraction, metrics and resolution policies."""

import re
from itertools import chain

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
from .resolution import ResolutionAdapter, top_symbols
from .resolution_paths import quoted_path
from .base import COMMON_METRICS, LanguageAdapter
from .parameters import parameter_children, parameter_node
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


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
    metrics=COMMON_METRICS,
    parameter_count=parameter_count,
)


class GoResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        return quoted_path(source) or source.strip()

    def import_item(self, ctx, file, source, path, position):
        if re.match(r"\s*\.\s+['\"]", source):
            return []
        alias = re.match(r"\s*([A-Za-z_$][\w$]*)\s+['\"]", source)
        binding = (
            alias[1]
            if alias and alias[1] not in {"import", "require"}
            else path.replace(".", "/").rstrip("/").rsplit("/", 1)[-1]
        )
        targets = self.import_files(ctx, file, path, position)
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
