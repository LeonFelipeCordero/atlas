"""Kotlin metric and resolution policies."""

import re
from collections import defaultdict

from ...domain.models import Symbol, file_key
from ...syntax import text
from ..receiver_syntax import child, enclosing, kotlin_bindings

from .resolution_paths import quoted_path

from dataclasses import replace

from tree_sitter import Node

from .java import JavaResolution

from .base import COMMON_METRICS, MetricAdapter

from .parameters import parameter_children, parameter_node

from ..resolution_contract import SCOPES


def alternative(node: Node) -> bool:
    parent = node.parent
    owner = parent.parent if parent is not None else None
    return bool(
        node.type == "if_expression"
        and parent is not None
        and parent.type == "control_structure_body"
        and owner is not None
        and owner.type == "if_expression"
        and owner.child_by_field_name("alternative") == parent
    )


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node, "function_value_parameters", "lambda_parameters")
    if parameters is None:
        # An implicit lambda input (it) cannot be inferred without type resolution.
        return (
            0
            if node.type == "lambda_literal"
            and any(child.type == "->" for child in node.children)
            else None
        )
    if parameters.has_error:
        return None
    entries = parameter_children(parameters)
    return sum(
        child.type
        in {"parameter", "variable_declaration", "multi_variable_declaration"}
        for child in entries
    )


METRICS = replace(
    COMMON_METRICS, extra_alternative=alternative, body_node="function_body"
)


class KotlinResolution(JavaResolution):
    receiver_bindings = staticmethod(kotlin_bindings)

    def select(self, identity, request, matches):
        if len(matches) <= 1:
            return matches
        if self.family not in identity.overload_indexes:
            identity.overload_indexes[self.family] = KotlinOverloads(identity.syntax)
        return select_overload(identity.overload_indexes[self.family], request, matches)

    def import_path(self, source: str) -> str:
        match = re.search(r"\bimport\s+([\w.]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "kotlin"
    scopes = SCOPES | {
        "lambda_literal",
        "function_body",
        "control_structure_body",
        "for_statement",
    }
    import_nodes = {"import_header"}
    receiver_class_nodes = {"object_creation_expression", "call_expression"}
    assignments = {"assignment"}
    declarations = {"variable_declaration"}
    loop_bindings = frozenset()
    member_writes = {"assignment", "prefix_expression", "postfix_expression"}
    receiver_updates = {"prefix_expression", "postfix_expression"}

    def write_target(self, node):
        if node.type in self.receiver_updates and not any(c.type in {"++", "--"} for c in node.children):
            return None
        return super().write_target(node)
    single_parameter_functions = {"lambda_expression"}

    def call_target(self, node):
        callee, receiver = super().call_target(node)
        if callee and callee.type == "navigation_expression":
            receiver = callee.named_children[0]
            suffix = callee.named_children[-1]
            callee = suffix.named_children[-1] if suffix.named_children else suffix
        return callee, receiver

    def binding(self, syntax, node, scope):
        if node.type == "property_declaration":
            return next(
                (c for c in node.named_children if c.type == "variable_declaration"),
                None,
            ), scope
        if node.type == "for_statement":
            target = next(
                (
                    c
                    for c in node.named_children
                    if c.type in {"variable_declaration", "multi_variable_declaration"}
                ),
                None,
            )
            return target, node
        return super().binding(syntax, node, scope)

    def import_name(self, source, path):
        return path

    def import_item(self, ctx, request):
        file, source, path = request.file, request.source, request.path
        alias = re.search(r"\bas\s*:?\s*([\w]+)", source)
        return [
            (
                alias[1] if alias else path.rsplit(".", 1)[-1],
                ctx.modules.declared(file, path),
                False,
            )
        ]

    def static_member(self, parent):
        return parent.kind in {"module", "object"}


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)


# Bounded overload selection, not compiler-style type inference. Only positional
# fixed arity and explicit, disjoint final types are used. Unknowns veto selection.
SCALARS = {"Boolean", "Byte", "Short", "Int", "Long", "Float", "Double", "Char", "String"}


class KotlinOverloads:
    """Analysis-local inventories; repeated calls never rescan the repository."""

    def __init__(self, syntax):
        self.syntax = syntax
        self.declarations = defaultdict(list)
        self.bindings = defaultdict(list)
        self.lexical = defaultdict(list)
        self.writes = defaultdict(list)
        self.unsupported = defaultdict(list)
        self.local_types = defaultdict(list)
        self.aliases = set()
        self.annotations = {}
        self.imports = {}
        self.known_imports = {}
        self.packages = {}
        for path, cache in syntax.items():
            if cache.file.source.language == "kotlin":
                self._index(path, cache)

    def _index(self, path, syntax):
        self.packages[path] = package_name(syntax)
        self.imports[path] = [unescaped_name(text(n)) for n in syntax.nodes if n.type == "import_header"]
        self.known_imports[path] = supported_import_syntax(syntax, self.imports[path])
        for symbol in syntax.file.symbols:
            canonical = ".".join(filter(None, [self.packages[path], symbol.qualified_name.split("::")[-1]]))
            self.declarations[unescaped_name(canonical)].append((syntax, symbol))
        for name, scope, node in syntax.bindings:
            self.lexical[path, unescaped_name(name)].append((scope, node))
        for node in syntax.nodes:
            self._index_binding(path, syntax, node)
            self._index_unsupported(path, syntax, node)
            self._index_type(path, syntax, node)

    def _index_binding(self, path, syntax, node):
        for binding in syntax.adapter.receiver_bindings(syntax, node):
            self.bindings[path, unescaped_name(binding.name)].append(binding)
        if node.type in syntax.adapter.assignments | syntax.adapter.receiver_updates:
            self.writes[path, unescaped_name(text(syntax.adapter.write_target(node)))].append(node)

    def _index_unsupported(self, path, syntax, node):
        if (node.type == "catch_block"
                or node.type == "class_parameter" and not syntax.adapter.receiver_bindings(syntax, node)):
            scope = node if node.type == "catch_block" else enclosing(node, {"class_declaration"})
            self.unsupported[path, unescaped_name(text(child(node, {"simple_identifier"})))].append(scope)

    def _index_type(self, path, syntax, node):
        if node.type not in {"class_declaration", "object_declaration", "type_alias"}:
            return
        name = unescaped_name(text(child(node, {"type_identifier"})))
        scope = syntax.scope(node)
        if scope != syntax.root:
            self.local_types[path, name].append(scope)
        if node.type == "type_alias":
            self.aliases.add(".".join(filter(None, [self.packages[path], name])))


def unsupported_binding(identity, syntax, name, position):
    return any(scope and scope.start_byte <= position < scope.end_byte
               for scope in identity.unsupported[syntax.file.source.path, name])


def select_overload(identity, request, matches: list[Symbol]) -> list[Symbol]:
    syntax = identity.syntax[request.file.source.path]
    if not supported_overload_set(identity, syntax, request, matches):
        return []
    call = syntax.node(request.call.start_byte, request.call.end_byte)
    arguments = positional_arguments(call)
    if arguments is None:
        return []
    candidates = arity_candidates(identity, matches, len(arguments))
    if candidates is None:
        return []
    if len(candidates) <= 1:
        return [symbol for symbol, _ in candidates]
    return typed_candidates(identity, syntax, call, arguments, candidates)


def supported_overload_set(identity, syntax, request, matches):
    # Bare matches may originate in the resolver's legacy global-name fallback.
    return (request.qualifier and len({s.parent_key for s in matches}) == 1
            and not unsupported_binding(identity, syntax, request.qualifier.split(".")[0], request.call.start_byte)
            and receiver_annotation_supported(identity, syntax, request, matches))


def receiver_annotation_supported(identity, syntax, request, matches):
    binding = nearest_argument_binding(identity, syntax, request.qualifier, request.call.start_byte)
    if binding is None or binding.inferred:
        return False
    receiver = explicit_type(identity, syntax, child(binding.node, {"user_type"}))
    if receiver is None or len(receiver) != 1:
        return False
    declarations = identity.declarations[receiver[0]]
    return len(declarations) == 1 and declarations[0][1].key == matches[0].parent_key


def arity_candidates(identity, matches, count):
    profiles = [(symbol, fixed_parameters(identity.syntax[symbol.file_path], symbol)) for symbol in matches]
    if any(parameters is None for _, parameters in profiles):
        return None
    return [(symbol, parameters) for symbol, parameters in profiles
            if parameters is not None and len(parameters) == count]


def typed_candidates(identity, syntax, call, arguments, candidates):
    actual = [argument_type(identity, syntax, argument, call) for argument in arguments]
    if not known_types(actual):
        return []
    expected = [(symbol, parameter_types(identity, symbol, parameters)) for symbol, parameters in candidates]
    if any(not known_types(kinds) for _, kinds in expected):
        return []
    return unique_match([symbol for symbol, kinds in expected if kinds == actual])


def unique_match(matches):
    return matches if len(matches) == 1 else []


def known_types(kinds):
    return all(kind is not None for kind in kinds)


def parameter_types(identity, symbol, parameters):
    syntax = identity.syntax[symbol.file_path]
    return [explicit_type(identity, syntax, child(p, {"user_type"})) for p in parameters]


def positional_arguments(call):
    if not valid_node(call, "call_expression"):
        return None
    suffix = child(call, {"call_suffix"})
    if suffix is None or any(c.type != "value_arguments" for c in suffix.named_children):
        return None
    values = child(suffix, {"value_arguments"})
    return argument_expressions(values) if values is not None else None


def valid_node(node, kind):
    return node is not None and node.type == kind and not node.has_error


def argument_expressions(values):
    arguments = [c for c in values.named_children if c.type != "comment"]
    if any(not positional_argument(a) for a in arguments):
        return None
    return [a.named_children[0] for a in arguments]


def positional_argument(argument):
    return (argument.type == "value_argument" and len(argument.named_children) == 1
            and argument.named_children[0].type != "spread_expression")


def fixed_parameters(syntax, symbol):
    node = syntax.node(symbol.start_byte, symbol.end_byte)
    if not valid_node(node, "function_declaration"):
        return None
    if any(c.type in {"type_parameters", "receiver_type"} for c in node.named_children):
        return None  # Generic functions and extension receivers need compiler rules.
    return fixed_parameter_entries(child(node, {"function_value_parameters"}))


def fixed_parameter_entries(parameters):
    if parameters is None or any(c.type == "=" for c in parameters.children):
        return None
    entries = [c for c in parameters.named_children if c.type != "comment"]
    return entries if all(c.type == "parameter" for c in entries) else None


def argument_type(identity, syntax, argument, call):
    if argument.type != "simple_identifier" or enclosing(call, {"lambda_literal"}) is not None:
        return None
    name = text(argument)
    if unsupported_binding(identity, syntax, name, call.start_byte):
        return None
    binding = nearest_argument_binding(identity, syntax, name, call.start_byte)
    if binding is None:
        return None
    if unsafe_argument_binding(identity, syntax, binding, call.start_byte):
        return None
    return explicit_type(identity, syntax, child(binding.node, {"user_type"}))


def nearest_argument_binding(identity, syntax, name, position):
    bindings = [b for b in identity.bindings[syntax.file.source.path, name] if syntax._visible(b.scope, position)]
    if not bindings:
        return None
    width = min(b.scope.end_byte - b.scope.start_byte for b in bindings)
    nearest = [b for b in bindings if b.scope.end_byte - b.scope.start_byte == width]
    return nearest[0] if len(nearest) == 1 else None


def unsafe_argument_binding(identity, syntax, binding, position):
    return (binding.member or binding.node.start_byte >= position or binding.inferred
            or argument_shadowed(identity, syntax, binding, position)
            or argument_written(identity, syntax, binding))


def argument_shadowed(identity, syntax, binding, position):
    width = binding.scope.end_byte - binding.scope.start_byte
    return any(syntax._visible(scope, position) and scope.end_byte - scope.start_byte <= width
               and not (node.start_byte <= binding.node.start_byte < node.end_byte)
               for scope, node in identity.lexical[syntax.file.source.path, unescaped_name(binding.name)])


def argument_written(identity, syntax, binding):
    return any(binding.scope.start_byte <= n.start_byte < binding.scope.end_byte
               for n in identity.writes[syntax.file.source.path, unescaped_name(binding.name)])


def explicit_type(identity, syntax, node):
    if node is None or not identity.known_imports[syntax.file.source.path]:
        return None
    key = (syntax.file.source.path, node.id)
    if key not in identity.annotations:
        identity.annotations[key] = _explicit_type(identity, syntax, node)
    return identity.annotations[key]


def _explicit_type(identity, syntax, node):
    if node.has_error:
        return None
    arguments = child(node, {"type_arguments"})
    name = text(node).split("<", 1)[0].strip()
    root = name.split(".")[0]
    if type_parameter_shadowed(node, root) or lexical_type_shadowed(identity, syntax, node, root):
        return None
    canonical = canonical_name(identity, syntax, name)
    if arguments is None:
        return (canonical,) if canonical and final_scalar(identity, canonical) else None
    return list_type(identity, syntax, canonical, arguments)


def lexical_type_shadowed(identity, syntax, node, name):
    return any(syntax._visible(scope, node.start_byte)
               for scope in identity.local_types[syntax.file.source.path, name])


def list_type(identity, syntax, canonical, arguments):
    projections = arguments.named_children
    if canonical != "kotlin.collections.List" or len(projections) != 1:
        return None
    projection = projections[0]
    if len(projection.children) != 1 or projection.children[0].type != "user_type":
        return None
    element = explicit_type(identity, syntax, projection.children[0])
    return (canonical, element) if element and len(element) == 1 else None


def type_parameter_shadowed(node, name):
    parent = node.parent
    while parent:
        if parent.type == "class_declaration" and child(parent, {"delegation_specifier"}):
            return True  # Inherited nested types are not a supported lexical type source.
        if generic_parameter(parent, name):
            return True
        parent = parent.parent
    return False


def generic_parameter(node, name):
    parameters = child(node, {"type_parameters"})
    return parameters and any(unescaped_name(text(child(p, {"type_identifier"}))) == name
                              for p in parameters.named_children)


def canonical_name(identity, syntax, name):
    if not re.fullmatch(r"\w+(?:\.\w+)*", name):
        return None
    if "." in name:
        return qualified_type_name(identity, syntax, name)
    imports = identity.imports[syntax.file.source.path]
    paths = imported_types(imports, name)
    if paths:
        return paths[0] if len(paths) == 1 else None
    local = ".".join(filter(None, [identity.packages[syntax.file.source.path], name]))
    if identity.declarations[local] or local in identity.aliases:
        return local
    return default_type(imports, name)


def qualified_type_name(identity, syntax, name):
    root = name.split(".")[0]
    local = ".".join(filter(None, [identity.packages[syntax.file.source.path], root]))
    imports = identity.imports[syntax.file.source.path]
    if identity.declarations[local] or local in identity.aliases or imported_types(imports, root):
        return None
    if any("*" in source for source in imports):
        return None
    return name


def imported_types(imports, name):
    return [m[1] for source in imports if (m := import_binding(source))
            and (m[2] or m[1].rsplit(".", 1)[-1]) == name]


def import_binding(source):
    return re.fullmatch(r"import\s+([\w.]+(?:\*)?)(?:\s+as\s+(\w+))?\s*;?", source)


def supported_import_syntax(syntax, imports):
    headers = [text(n) for n in syntax.nodes if n.type == "package_header"]
    return (all(import_binding(source) for source in imports)
            and all(re.fullmatch(r"package\s+[\w.]+\s*;?", source) for source in headers))


def unescaped_name(value):
    return value.replace("`", "")


def package_name(syntax):
    header = next((n for n in syntax.nodes if n.type == "package_header"), None)
    if header is None:
        return ""
    identifier = child(header, {"identifier"})
    return ".".join(unescaped_name(text(n)) for n in identifier.named_children
                    if n.type == "simple_identifier") if identifier else ""


def default_type(imports, name):
    if any("*" in source for source in imports):
        return None
    if name in SCALARS:
        return "kotlin." + name
    return "kotlin.collections.List" if name == "List" else None


def final_scalar(identity, canonical):
    if canonical in {"kotlin." + name for name in SCALARS}:
        return True
    matches = identity.declarations[canonical]
    if len(matches) != 1:
        return False
    syntax, symbol = matches[0]
    return closed_class(symbol, syntax.node(symbol.start_byte, symbol.end_byte))


def closed_class(symbol, node):
    if (symbol.kind != "class" or symbol.parent_key != file_key(symbol.file_path)
            or node is None or node.has_error):
        return False
    if any(c.type in {"delegation_specifier", "type_parameters"} for c in node.named_children):
        return False
    modifiers = child(node, {"modifiers"})
    return not modifiers or not ({"open", "abstract", "sealed", "inner"} & set(text(modifiers).split()))
