"""Language-neutral syntax cache and conservative lexical binding scan."""

from functools import cached_property
from itertools import chain
from typing import TYPE_CHECKING

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from ..domain.models import ParsedFile, Symbol
from .syntax import field, text, walk

from .resolution_contract import FUNCTIONS as FUNCTIONS, SCOPES as SCOPES

PARAMETERS = {
    "parameters",
    "formal_parameters",
    "parameter_list",
    "function_value_parameters",
    "lambda_parameters",
    "closure_parameters",
    "inferred_parameters",
}
IDENTIFIERS = {
    "identifier",
    "simple_identifier",
    "field_identifier",
    "shorthand_property_identifier_pattern",
}


def names(node: Node | None) -> set[str]:
    """Collect binding patterns, never member accesses or type annotations."""
    if node is None:
        return set()
    if node.type in IDENTIFIERS:
        return {text(node)}
    if node.type in {"attribute", "member_expression", "field_expression", "subscript"}:
        return set()
    if node.type == "pair_pattern":
        return names(field(node, "value"))
    return _structured_names(node)


def _structured_names(node: Node) -> set[str]:
    declared = node.children_by_field_name("name")
    if node.type == "parameter_declaration" and declared:
        return set().union(*(names(child) for child in declared))
    target = field(node, "pattern", "name", "declarator", "left")
    if target:
        return names(target)
    return _child_names(node)


def _child_names(node: Node) -> set[str]:
    if node.type in {
        "typed_parameter",
        "default_parameter",
        "typed_default_parameter",
        "parameter",
        "variable_declaration",
    }:
        return names(
            next(
                (child for child in node.named_children if child.type in IDENTIFIERS),
                None,
            )
        )
    if "pattern" in node.type or node.type in PARAMETERS | {
        "tuple",
        "list",
        "expression_list",
        "directly_assignable_expression",
        "parenthesized_declarator",
        "multi_variable_declaration",
    }:
        return set().union(*(names(child) for child in node.named_children))
    return set()


if TYPE_CHECKING:
    from ..adapters.resolution_policy import ResolutionAdapter


def _same_import(node: Node, source: str) -> bool:
    return text(node).strip().rstrip(";") == source.strip().rstrip(";")


def _class_or_function(node: Node) -> Node | None:
    parent = node.parent
    while parent and parent.type not in FUNCTIONS | {
        "class_definition",
        "class_declaration",
    }:
        parent = parent.parent
    return parent


class Syntax:
    """One parsed tree per file; binding checks reject any visible rebinding."""

    def __init__(self, file: ParsedFile, adapter: "ResolutionAdapter"):
        self.file = file
        self.adapter = adapter
        self.scopes = self.adapter.scopes

    @cached_property
    def root(self) -> Node | None:
        try:
            return (
                get_parser(self.file.source.language)
                .parse(
                    self.file.source.source.decode("utf-8", errors="replace").encode("utf-8")
                )
                .root_node
            )
        except Exception:
            return None

    @cached_property
    def nodes(self) -> list[Node]:
        return list(walk(self.root)) if self.root else []

    @cached_property
    def spans(self) -> dict[tuple[int, int], Node]:
        return {(n.start_byte, n.end_byte): n for n in self.nodes}

    @cached_property
    def imports(self) -> list[tuple[str, Node]]:
        return self.adapter.lexical_imports(self)

    @cached_property
    def bindings(self) -> list[tuple[str, Node, Node]]:
        bindings: list[tuple[str, Node, Node]] = []
        for node in self.nodes:
            self._bindings(node, bindings)
        return bindings

    def node(self, start: int, end: int) -> Node | None:
        return self.spans.get((start, end))

    def scope(self, node: Node) -> Node:
        parent = node.parent
        while parent and parent.type not in self.scopes:
            parent = parent.parent
        return parent or self.root or node

    def _bindings(self, node: Node, bindings: list[tuple[str, Node, Node]]) -> None:
        scope = self.scope(node)
        if node.type in PARAMETERS:
            self._record_bindings(
                chain.from_iterable(names(child) for child in node.named_children),
                scope,
                node,
                bindings,
            )
            return
        if node.type in self.adapter.single_parameter_functions:
            parameter = field(node, "parameter", "parameters")
            if parameter and parameter.type in IDENTIFIERS:
                bindings.append((text(parameter), node, parameter))
            return
        target, scope = self.adapter.binding(self, node, scope)
        self._record_bindings(names(target), scope, node, bindings)

    def _record_bindings(self, names, scope: Node, node: Node, bindings) -> None:
        bindings.extend((name, scope, node) for name in names)

    def _visible(self, scope: Node, position: int) -> bool:
        return scope.start_byte <= position < scope.end_byte and self.adapter.visible(
            self, scope, position
        )

    def _declaration_allowed(
        self, name: str, node: Node, position: int, allowed: list[Symbol]
    ) -> bool:
        if any(
            node.start_byte <= s.start_byte and s.end_byte <= node.end_byte
            for s in allowed
        ):
            return True
        return self.adapter.declaration_allowed(self, name, node, position)

    def shadowed(
        self, name: str, position: int, allowed: list[Symbol] | None = None
    ) -> bool:
        allowed = allowed or []
        if self.adapter.import_shadowed(self, name, position):
            return True
        return any(
            binding == name
            and self._visible(scope, position)
            and not self._declaration_allowed(name, node, position, allowed)
            for binding, scope, node in self.bindings
        )

    def _imports_on_line(self, line: int) -> list[Node]:
        return [
            node
            for node in self.nodes
            if node.start_point.row + 1 == line and self.adapter.is_import_node(node)
        ]

    def import_node(self, line: int, source: str | None = None) -> Node | None:
        candidates = self._imports_on_line(line)
        if source is not None:
            exact = [node for node in candidates if _same_import(node, source)]
            if exact:
                candidates = exact
        return candidates[0] if len(candidates) == 1 else None

    def import_scope(self, line: int, source: str | None = None) -> Node | None:
        node = self.import_node(line, source)
        return self.scope(node) if node else self.root

    def class_rebound(self, symbol: Symbol, name: str) -> bool:
        for binding, _, node in self.bindings:
            if binding != name or node.type in self.adapter.rebound_declarations:
                continue
            parent = _class_or_function(node)
            if (
                parent
                and parent.start_byte == symbol.start_byte
                and parent.end_byte == symbol.end_byte
            ):
                return True
        return False

    def member_rebound(self, qualifier: str, name: str) -> bool:
        for node in self.nodes:
            if node.type not in self.adapter.member_writes:
                continue
            if text(field(node, "left")).replace(" ", "") == qualifier + "." + name:
                return True
        return False

    def static(self, symbol: Symbol) -> bool:
        return self.adapter.static(self, symbol)
