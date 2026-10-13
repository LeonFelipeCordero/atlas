"""Javascript metric and resolution policies."""

import re


from itertools import chain


from tree_sitter import Node

from ..receiver_syntax import script_bindings

from ...domain.models import Symbol

from .resolution import ResolutionAdapter, relative_targets, top_symbols

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import parameter_children, parameter_node
from .script_resolution import inherited_members, member_mutation, member_write, same_declaration_group

from ..resolution_contract import FUNCTIONS, CallTarget, ImportRequest

from ...syntax import field, text


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node)
    if parameters is None or parameters.has_error:
        return None
    if parameters.type == "identifier":
        return 1
    return sum(
        child.type != "this" and (field(child, "pattern") or child).type != "this"
        for child in parameter_children(parameters)
    )


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


def _import_clause(source: str) -> str:
    clause = re.search(r"\bimport\s+(.+?)\s+from\b", source, re.S)
    return clause[1].strip() if clause else ""


def _named_import(ctx, request: ImportRequest, part: str):
    match = re.fullmatch(r"\s*(type\s+)?([\w$]+)(?:\s+as\s+([\w$]+))?\s*", part)
    if not match:
        return None
    type_only = _import_clause(request.source).startswith("type ")
    targets = [] if type_only or match[1] else ctx._members(request, match[2])
    return match[3] or match[2], targets, False


def _named_imports(ctx, request: ImportRequest, raw: str):
    named = re.search(r"\{([^}]+)\}", raw)
    if not named:
        return []
    return [
        entry
        for part in named[1].split(",")
        if (entry := _named_import(ctx, request, part)) is not None
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


def _field_masks_method(child: Node, name: str, implementations: set[str]) -> bool:
    target = field(child, "name", "property")
    if target is None:
        return False
    if target.type == "computed_property_name":
        return True
    return text(target) == name and _non_callable_member(child, name, implementations)


def _non_callable_member(child: Node, name: str, implementations: set[str]) -> bool:
    return (child.type in {"field_definition", "public_field_definition"}
            or child.type in {"method_signature", "abstract_method_signature"} and name not in implementations
            or any(c.type in {"get", "set"} for c in child.children))


def _script_own_field(syntax, parent, name):
    node = syntax.node(parent.start_byte, parent.end_byte)
    body = field(node, "body")
    if body is None:
        return False
    children = body.named_children
    implementations = {text(field(c, "name")) for c in children if field(c, "body") is not None}
    return any(_field_masks_method(child, name, implementations) for child in children)


def _receiver_alias(node: Node, receivers: set[str]) -> str | None:
    if node.type not in {"variable_declarator", "assignment_expression"}:
        return None
    if text(field(node, "value", "right")) not in receivers:
        return None
    target = field(node, "name", "left")
    return text(target) if target is not None and target.type == "identifier" else None


def _receiver_mutation(syntax, node: Node, receivers: set[str], name: str) -> bool:
    return (node.type in syntax.adapter.member_writes
            and member_write(text(syntax.adapter.write_target(node)), receivers, name)
            or member_mutation(node, receivers))


def _receiver_aliases(nodes: list[Node], receivers: set[str]) -> set[str]:
    return {alias for n in nodes if (alias := _receiver_alias(n, receivers)) is not None}


def _method_group(matches: list[Symbol]) -> bool:
    return same_declaration_group(matches) and all(s.kind == "method" for s in matches)


def _plain_method(node: Node | None) -> bool:
    return (node is not None and node.type == "method_definition"
            and field(node, "body") is not None
            and not any(c.type in {"get", "set"} for c in node.children))


def _script_mutation(syntax, parent, name):
    receivers = {parent.name, parent.name + ".prototype"}
    for _ in syntax.nodes:
        aliases = _receiver_aliases(syntax.nodes, receivers)
        if aliases <= receivers:
            break
        receivers |= aliases
    return any(_receiver_mutation(syntax, node, receivers, name) for node in syntax.nodes)


class JavaScriptResolution(ResolutionAdapter):
    receiver_bindings = staticmethod(script_bindings)
    def import_path(self, source: str) -> str:
        return quoted_path(source) or source.strip()

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
    member_writes = assignments | {"update_expression", "unary_expression"}
    validate_receiver_initializer = True
    single_parameter_functions = {"arrow_function"}

    def instance_members(self, resolver, parent, name):
        return inherited_members(resolver, parent, name)

    def select(self, identity, request, matches):
        if len(matches) <= 1:
            return matches
        if not _method_group(matches):
            return []
        nodes = [identity.syntax[s.file_path].node(s.start_byte, s.end_byte) for s in matches]
        if not all(_plain_method(node) for node in nodes):
            return []
        if len({identity.syntax[s.file_path].static(s) for s in matches}) != 1:
            return []
        return [max(matches, key=lambda s: s.start_byte)]

    def call_target(self, node):
        if node and node.type == "new_expression":
            return field(node, "constructor", "type"), None
        return super().call_target(node)

    def normalized_call(self, call, callee, receiver):
        if call.relationship == "REFERENCES":
            return CallTarget(callee, receiver, call.name, call.qualifier)
        return super().normalized_call(call, callee, receiver)

    def receiver_type_allowed(self, syntax, name, member):
        return super().receiver_type_allowed(syntax, name, member) and not syntax.member_rebound(name + ".prototype", member)

    def receiver_class_allowed(self, syntax, callee, member):
        return not syntax.member_rebound(text(callee) + ".prototype", member)

    def member_overwritten(self, syntax, parent, name):
        return super().member_overwritten(
            syntax, parent, name
        ) or _script_mutation(syntax, parent, name) or _script_own_field(syntax, parent, name)

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
            relative_targets(ImportRequest(source, name), files, index_only=True)
            if name.startswith(".") and "/" in name
            else []
        )

    def members(self, ctx, request: ImportRequest, name):
        targets = self.import_files(ctx, request)
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

    def import_item(self, ctx, request: ImportRequest):
        raw = _import_clause(request.source)
        if not raw:
            return []
        type_only = raw.startswith("type ")
        raw = raw.removeprefix("type ")
        result = []
        result.extend(self._namespace_import(ctx, request, raw))
        result.extend(_named_imports(ctx, request, raw))
        default = re.match(r"([\w$]+)(?:\s*,|$)", raw)
        if default:
            result.append(
                (
                    default[1],
                    [] if type_only else ctx._members(request, "default"),
                    False,
                )
            )
        return result

    def _namespace_import(self, ctx, request: ImportRequest, raw):
        type_only = _import_clause(request.source).startswith("type ")
        namespace = re.search(r"\*\s+as\s+([\w$]+)", raw)
        if not namespace:
            return []
        targets = list(
            chain.from_iterable(self.namespace_exports(ctx, request.file, request.path).values())
        )
        return [(namespace[1], [] if type_only else targets, True)]

    def namespace_members(self, ctx, request: ImportRequest, targets):
        return self.namespace_exports(ctx, request.file, request.path) if targets else {}

    def implicit_receiver(self, resolver, request, method):
        if request.qualifier != "this":
            return True
        file = request.file
        ancestors = resolver.ancestors(request.owner)
        nested = ancestors[: ancestors.index(method)]
        return all(
            (node := resolver.syntax[file.source.path].node(s.start_byte, s.end_byte))
            is not None
            and node.type == "arrow_function"
            for s in nested
        )


METRICS = COMMON_METRICS


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
