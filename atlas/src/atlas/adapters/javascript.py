"""Javascript extraction, metrics and resolution policies."""

import re
from collections.abc import Iterator
from itertools import chain
from typing import Literal
from tree_sitter import Node
from ..domain.models import ParsedFile, Symbol
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    normalize_call as shared_normalize_call,
    InheritancePolicy,
    modifier_metadata,
    field,
    text,
    walk,
)
from .resolution import ResolutionAdapter, relative_targets, top_symbols
from ..extraction.resolution_syntax import FUNCTIONS

SCRIPT_CALLBACKS = frozenset(
    {"arrow_function", "function_expression", "generator_function"}
)
SCRIPT_QUERY = """
[(arrow_function) (function_expression) (generator_function)] @definition.function
"""
CALL_TYPES = frozenset({"call_expression", "new_expression"})
INHERITANCE = InheritancePolicy(
    frozenset({"extends_clause", "extends_type_clause", "implements_clause"}),
    complete_header=True,
    heritage_clause="class_heritage",
)
JSX_TAGS = frozenset({"jsx_opening_element", "jsx_self_closing_element"})


def _component(node: Node) -> bool:
    if node.type == "member_expression":
        return True  # Namespaces may start lowercase: <cards.CoffeeCard />.
    name = text(node)
    return (
        node.type == "identifier"
        and bool(name)
        and not ("a" <= name[0] <= "z" or "-" in name)
    )


def is_jsx_site(node: Node) -> bool:
    parent = node.parent
    return bool(
        parent is not None
        and parent.type in JSX_TAGS
        and parent.child_by_field_name("name") == node
    )


def call_sites(root: Node) -> Iterator[CallSite]:
    for node in walk(root):
        if node.type in CALL_TYPES or is_jsx_site(node) and _component(node):
            yield node, 0, False, ()


def normalize_call(site: CallSite) -> CallTarget:
    node = site[0]
    if is_jsx_site(node):
        name = text(node)
        qualifier, separator, member = name.rpartition(".")
        return (member, False, qualifier) if separator else (name, True, None)
    return shared_normalize_call(site)


def call_relationship(site: CallSite) -> Literal["CALLS", "REFERENCES"]:
    return "REFERENCES" if is_jsx_site(site[0]) else "CALLS"


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(node, frozenset({"public", "private", "protected"}))


def unparenthesized(node: Node) -> Node:
    """Only a single expression in parentheses is transparent, not a sequence."""
    while node.type == "parenthesized_expression":
        expressions = _expressions(node)
        if len(expressions) != 1:
            break
        node = expressions[0]
    return node


def _expressions(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type != "comment"]


def script_declaration(node: Node) -> DeclarationCarrier:
    expression = unparenthesized(node)
    if expression.type in SCRIPT_CALLBACKS:
        node = expression
    value_field = "right" if node.type == "assignment_expression" else "value"
    value = node.child_by_field_name(value_field)
    value = unparenthesized(value) if value is not None else None
    if node.type in {"variable_declarator", "assignment_expression", "pair"}:
        if value is not None and value.type in SCRIPT_CALLBACKS:
            node = value
    if node.type in SCRIPT_CALLBACKS:
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


def _local_export(node: Node) -> bool:
    return (
        node.type == "export_statement"
        and not field(node, "source")
        and not re.match(r"export\s+type\b", text(node))
    )


def _export_declaration(node: Node, declarations: list[Symbol]):
    declaration = field(node, "declaration", "value")
    if declaration is None:
        return []
    default = bool(re.match(r"export\s+default\b", text(node)))
    matches = _declaration_symbols(declaration, declarations)
    return [("default" if default else symbol.name, [symbol]) for symbol in matches]


def _declaration_symbols(node: Node, declarations: list[Symbol]) -> list[Symbol]:
    return [
        symbol
        for symbol in declarations
        if symbol.name == text(node)
        or node.start_byte <= symbol.start_byte < node.end_byte
    ]


def _export_specifiers(node: Node):
    clauses = [child for child in node.named_children if child.type == "export_clause"]
    return chain.from_iterable(clause.named_children for clause in clauses)


def _export_specifier(spec: Node, declarations: list[Symbol]):
    if text(spec).startswith("type "):
        return None
    original = text(field(spec, "name"))
    alias = text(field(spec, "alias")) or original
    return alias, [symbol for symbol in declarations if symbol.name == original]


def _export_entries(node: Node, declarations: list[Symbol]):
    entries = _export_declaration(node, declarations)
    entries.extend(
        entry
        for spec in _export_specifiers(node)
        if (entry := _export_specifier(spec, declarations)) is not None
    )
    return entries


def _extend_exports(result: dict[str, list[Symbol]], entries) -> None:
    for name, symbols in entries:
        result.setdefault(name, []).extend(symbols)


def _unique_symbols(symbols: list[Symbol]) -> list[Symbol]:
    return list({symbol.key: symbol for symbol in symbols}.values())


def export_bindings(file, syntax) -> dict[str, list[Symbol]]:
    result: dict[str, list[Symbol]] = {}
    declarations = top_symbols(file)
    for node in syntax.nodes:
        if _local_export(node):
            _extend_exports(result, _export_entries(node, declarations))
    return {name: _unique_symbols(symbols) for name, symbols in result.items()}


def _named_import(ctx, file, path, part, type_only):
    match = re.fullmatch(r"\s*(type\s+)?([\w$]+)(?:\s+as\s+([\w$]+))?\s*", part)
    if not match:
        return None
    targets = [] if type_only or match[1] else ctx._members(file, path, match[2])
    return match[3] or match[2], targets, False


def _named_imports(ctx, file, path, raw, type_only):
    named = re.search(r"\{([^}]+)\}", raw)
    if not named:
        return []
    return [
        entry
        for part in named[1].split(",")
        if (entry := _named_import(ctx, file, path, part, type_only)) is not None
    ]


def _has_type_modifier(node: Node) -> bool:
    return any(child.type == "type" for child in node.children)


def _named_import_specifiers(clause: Node | None) -> list[Node]:
    if clause is None or len(clause.named_children) != 1:
        return []
    named = clause.named_children[0]
    if named.type != "named_imports":
        return []
    return [c for c in named.named_children if c.type == "import_specifier"]


def _type_only_named_clause(node: Node) -> bool:
    clause = next((c for c in node.named_children if c.type == "import_clause"), None)
    specifiers = _named_import_specifiers(clause)
    return bool(specifiers) and all(map(_has_type_modifier, specifiers))


class JavaScriptResolution(ResolutionAdapter):
    family = "javascript"
    import_nodes = {"import_statement"}
    skip_type_scope = True
    self_qualifiers = {"this"}
    constructors = {"new_expression"}
    receiver_class_nodes = {"new_expression"}
    receiver_names = {"this"}
    member_nodes = {"member_expression": (("object",), ("property",))}
    assignments = {"assignment_expression", "augmented_assignment_expression"}
    declarations = {"variable_declarator"}
    loop_bindings = {"for_statement", "for_in_statement"}
    static_nodes = {"static"}
    static_containers = {"modifiers"}
    member_writes = {"assignment_expression"}
    single_parameter_functions = {"arrow_function"}

    def call_target(self, node):
        if node and node.type == "new_expression":
            return field(node, "constructor", "type"), None
        return super().call_target(node)

    def normalized_call(self, node, call, callee, receiver):
        if call.relationship == "REFERENCES":
            return callee, receiver, call.name, call.qualifier
        return super().normalized_call(node, call, callee, receiver)

    def receiver_class_allowed(self, syntax, callee, member):
        return not syntax.member_rebound(text(callee) + ".prototype", member)

    def member_overwritten(self, syntax, parent, name):
        return super().member_overwritten(
            syntax, parent, name
        ) or syntax.member_rebound(parent.name + ".prototype", name)

    def binding(self, syntax, node, scope):
        if node.type == "function_declaration":
            return field(node, "name"), scope
        if node.type == "function_expression":
            return field(node, "name"), node
        target, scope = super().binding(syntax, node, scope)
        if (
            node.type == "variable_declarator"
            and node.parent
            and text(node.parent).startswith("var ")
        ):
            while scope.parent and scope.type not in FUNCTIONS:
                scope = syntax.scope(scope)
        return target, scope

    def paths(self, source, name, files):
        return (
            relative_targets(source, name, files, index_only=True)
            if name.startswith(".") and "/" in name
            else []
        )

    def members(self, ctx, file, path, name, position):
        targets = self.import_files(ctx, file, path, position)
        if len(targets) != 1:
            return []
        return export_bindings(targets[0], ctx.syntax[targets[0].source.path]).get(
            name, []
        )

    def namespace_exports(self, ctx, file, path):
        result: dict[str, list[Symbol]] = {}
        for target in ctx.files(file, path):
            _extend_exports(
                result, export_bindings(target, ctx.syntax[target.source.path]).items()
            )
        return result

    def import_type_only(self, node: Node | None) -> bool:
        if node is None or node.type != "import_statement":
            return False
        if _has_type_modifier(node):
            return True
        return _type_only_named_clause(node)

    def import_item(
        self, ctx, file: ParsedFile, source: str, path: str, position: int | None
    ):
        clause = re.search(r"\bimport\s+(.+?)\s+from\b", source, re.S)
        if not clause:
            return []
        raw = clause[1].strip()
        type_only = raw.startswith("type ")
        raw = raw.removeprefix("type ")
        result = []
        result.extend(self._namespace_import(ctx, file, path, raw, type_only))
        result.extend(_named_imports(ctx, file, path, raw, type_only))
        default = re.match(r"([\w$]+)(?:\s*,|$)", raw)
        if default:
            result.append(
                (
                    default[1],
                    [] if type_only else ctx._members(file, path, "default"),
                    False,
                )
            )
        return result

    def _namespace_import(self, ctx, file, path, raw, type_only):
        namespace = re.search(r"\*\s+as\s+([\w$]+)", raw)
        if not namespace:
            return []
        targets = list(
            chain.from_iterable(self.namespace_exports(ctx, file, path).values())
        )
        return [(namespace[1], [] if type_only else targets, True)]

    def namespace_members(self, ctx, file, path, targets):
        return self.namespace_exports(ctx, file, path) if targets else {}

    def implicit_receiver(self, resolver, file, qualifier, call, ancestors, method):
        if qualifier != "this":
            return True
        nested = ancestors[: ancestors.index(method)]
        return all(
            (node := resolver.syntax[file.source.path].node(s.start_byte, s.end_byte))
            is not None
            and node.type == "arrow_function"
            for s in nested
        )
