"""Python extraction, metrics and resolution policies."""

import re
from dataclasses import replace
from pathlib import PurePosixPath
from typing import cast

from tree_sitter import Node
from ..domain.models import ParsedFile, Symbol
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    call_sites as shared_call_sites,
    InheritancePolicy,
    text,
    field,
)
from .resolution import ResolutionAdapter, top_symbols, path_target_key
from .resolution_paths import quoted_path
from .base import COMMON_METRICS, LanguageAdapter
from .parameters import count_parameters, parameter_children, parameter_node

QUERY = "\n(lambda) @definition.function\n"
CALLBACK_TYPES = frozenset({"lambda"})
CALL_TYPES = frozenset({"call"})
INHERITANCE = InheritancePolicy(frozenset(), superclass_field="superclasses")


def declaration(node: Node) -> DeclarationCarrier:
    if node.type == "decorated_definition":
        node = node.child_by_field_name("definition") or node
    if node.type == "lambda":
        return callback_carrier(node, callback_binding(node))
    carrier = named_carrier(node)
    if node.parent is not None and node.parent.type == "decorated_definition":
        decorators = tuple(
            text(child)
            for child in node.parent.named_children
            if child.type == "decorator"
        )
        return DeclarationCarrier(node, carrier.name, decorators=decorators)
    return carrier


def call_sites(root: Node):
    return shared_call_sites(root, CALL_TYPES)


def irrefutable_pattern(pattern: Node) -> bool:
    handler = _PATTERN_CHECKS.get(pattern.type)
    return handler(pattern) if handler is not None else False


def _single_pattern(pattern: Node) -> bool:
    children = pattern.named_children
    return len(children) == 1 and irrefutable_pattern(children[0])


def _case_pattern(pattern: Node) -> bool:
    if not pattern.named_children:
        return any(child.type == "_" for child in pattern.children)
    return _single_pattern(pattern)


def _capture_pattern(pattern: Node) -> bool:
    children = pattern.named_children
    return len(children) == 1 and children[0].type == "identifier"


def _as_pattern(pattern: Node) -> bool:
    children = pattern.named_children
    return bool(children) and irrefutable_pattern(children[0])


def _union_pattern(pattern: Node) -> bool:
    return any(child.type == "_" for child in pattern.children) or any(
        irrefutable_pattern(child) for child in pattern.named_children
    )


def _tuple_pattern(pattern: Node) -> bool:
    return (
        not any(child.type == "," for child in pattern.children)
        and _single_pattern(pattern)
    )


_PATTERN_CHECKS = {
    "case_pattern": _case_pattern,
    "dotted_name": _capture_pattern,
    "as_pattern": _as_pattern,
    "union_pattern": _union_pattern,
    "tuple_pattern": _tuple_pattern,
}


def case_decision(node: Node) -> bool:
    pattern = next(
        (child for child in node.named_children if child.type == "case_pattern"), None
    )
    return pattern is None or not irrefutable_pattern(pattern)


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node)
    if parameters is None:
        return 0 if node.type == "lambda" else None
    count = count_parameters(parameters, frozenset({"positional_separator", "keyword_separator"}))
    entries = parameter_children(parameters)
    if count is None or not entries:
        return count
    return count - int(_python_method(node) and _python_receiver(entries[0]))


def _python_owner(node: Node) -> tuple[Node | None, list[Node]]:
    owner = node.parent
    decorators: list[Node] = []
    if owner is not None and owner.type == "decorated_definition":
        decorators = [
            child for child in owner.named_children if child.type == "decorator"
        ]
        owner = owner.parent
    return owner, decorators


def _python_method(node: Node) -> bool:
    owner, decorators = _python_owner(node)
    if any(_python_static(decorator) for decorator in decorators):
        return False
    return (
        owner is not None
        and owner.type == "block"
        and owner.parent is not None
        and owner.parent.type == "class_definition"
    )


def _python_static(decorator: Node) -> bool:
    expression = next(iter(parameter_children(decorator)), None)
    return text(expression) == "staticmethod"


def _python_receiver(first: Node) -> bool:
    if first.type == "typed_parameter":
        first = next(iter(first.named_children), first)
    return first.type in {
        "identifier",
        "default_parameter",
        "typed_default_parameter",
    }


METRICS = replace(COMMON_METRICS, decision_overrides={"case_clause": case_decision})
ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    inheritance_policy=INHERITANCE,
    metrics=METRICS,
    parameter_count=parameter_count,
)


COMPREHENSIONS = {
    "list_comprehension",
    "set_comprehension",
    "dictionary_comprehension",
    "generator_expression",
}


def _in_comprehension_iterable(scope: Node, position: int) -> bool:
    clause = next((c for c in scope.named_children if c.type == "for_in_clause"), None)
    iterable = field(clause, "right") if clause else None
    return bool(iterable and iterable.start_byte <= position < iterable.end_byte)


def _hides_class_scope(syntax, parent: Node, position: int) -> bool:
    if parent.type in {"function_definition", "lambda", "class_definition"}:
        body = field(parent, "body")
        if body and body.start_byte <= position < body.end_byte:
            return True
    return parent.type in COMPREHENSIONS and syntax._visible(parent, position)


def _self_parameter(parameters: Node | None) -> bool:
    return bool(
        parameters
        and parameters.named_children
        and text(parameters.named_children[0]) == "self"
    )


def _bare_relative_import(source: str, path: str) -> bool:
    return bool(re.fullmatch(r"\.+", path)) and source.lstrip().startswith("from ")


def _package_root(package: PurePosixPath, packages: set[PurePosixPath]) -> PurePosixPath:
    while package.parts and package in packages:
        package = package.parent
    return package


def _source_roots(files: list[ParsedFile]) -> set[PurePosixPath]:
    packages = {
        PurePosixPath(file.source.path).parent
        for file in files
        if PurePosixPath(file.source.path).name == "__init__.py"
    }
    roots = {PurePosixPath(".")} | {_package_root(package, packages) for package in packages}
    for file in files:
        roots.update(_src_roots(PurePosixPath(file.source.path)))
    return roots


def _src_roots(path: PurePosixPath) -> set[PurePosixPath]:
    return {parent for parent in path.parents if parent.name == "src"}


def _module_name(path: PurePosixPath, root: PurePosixPath) -> str:
    if not path.is_relative_to(root):
        return ""
    module = path.relative_to(root).with_suffix("")
    if module.name == "__init__":
        module = module.parent
    return ".".join(module.parts)


def _index_modules(index: dict[str, list[ParsedFile]], file: ParsedFile, roots) -> None:
    for root in roots:
        name = _module_name(PurePosixPath(file.source.path), root)
        if name:
            index.setdefault(name, []).append(file)


def _import_attribute(syntax, node: Node, name: str, excluded: int | None) -> bool:
    if node.type not in syntax.adapter.import_nodes or node.start_byte == excluded:
        return False
    if syntax.scope(node) != syntax.root:
        return False
    return any((alias or imported.split(".")[0]) == name for imported, alias in _import_names(node))


def _runtime_assignment(node: Node) -> bool:
    return node.type != "assignment" or field(node, "right") is not None


def _assigned_attribute(syntax, name: str) -> bool:
    return any(
        alias == name and scope == syntax.root and _runtime_assignment(node)
        for alias, scope, node in syntax.bindings
    )


def _package_parent(files: list[ParsedFile]) -> bool:
    return not files or len(files) == 1 and PurePosixPath(files[0].source.path).name == "__init__.py"


def _absolute_module_files(index: dict[str, list[ParsedFile]], path: str) -> list[ParsedFile]:
    parts = path.split(".")
    for length in range(1, len(parts)):
        if not _package_parent(index.get(".".join(parts[:length]), [])):
            return []
    matches = index.get(path, [])
    return matches if len(matches) == 1 else []


def _module_attribute(ctx, file, path: str, name: str, position: int | None) -> bool:
    modules = ctx.files(file, path)
    if len(modules) != 1:
        return False
    syntax = ctx.syntax[modules[0].source.path]
    assigned = _assigned_attribute(syntax, name)
    excluded = position if modules[0].source.path == file.source.path else None
    return assigned or any(_import_attribute(syntax, node, name, excluded) for node in syntax.nodes)


def _child_module_files(ctx, file, path: str, name: str, position: int | None) -> list[ParsedFile]:
    if not _package_parent(ctx.files(file, path)):
        return []
    if ctx._members(file, path, name) or _module_attribute(ctx, file, path, name, position):
        return []
    return ctx.files(file, _child_path(path, name))


def _child_path(path: str, name: str) -> str:
    return path + ("" if path.endswith(".") else ".") + name


def _import_names(node: Node) -> list[tuple[str, str]]:
    return [
        (text(field(child, "name") or child), text(field(child, "alias")))
        for child in node.children_by_field_name("name")
    ]


def _import_node(ctx, file, position):
    return next(
        (
            node
            for node in ctx.syntax[file.source.path].nodes
            if node.start_byte == position
            and node.type in {"import_statement", "import_from_statement"}
        ),
        None,
    )


class PythonResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        match = re.search(r"\bfrom\s+([\w.]+)|\bimport\s+([\w.]+)", source)
        path = next((part for part in match.groups() if part), "") if match else source.strip()
        return quoted_path(source) or path

    family = "python"
    scopes = {"function_definition", "lambda", "class_definition"} | COMPREHENSIONS
    import_nodes = {"import_statement", "import_from_statement"}
    skip_type_scope = True
    self_qualifiers = {"self"}
    receiver_class_nodes = {"call"}
    member_nodes = {"attribute": (("object",), ("attribute",))}
    assignments = {"assignment", "augmented_assignment", "named_expression"}
    loop_bindings = {"for_statement", "for_in_clause"}
    member_writes = {"assignment", "augmented_assignment"}
    rebound_declarations = {"function_definition", "class_definition"}

    def module_index(self, repository, syntax) -> dict[str, list[ParsedFile]]:
        files = [
            file for file in repository.files
            if file.source.language == "python" and file.source.path.endswith(".py")
        ]
        roots = _source_roots(files)
        index: dict[str, list[ParsedFile]] = {}
        for file in files:
            _index_modules(index, file, roots)
        return index

    def import_files(self, ctx, file, path, position):
        if path.startswith("."):
            return ctx.path_files(file, path)
        index = cast(dict[str, list[ParsedFile]], ctx.modules.indexes[file.source.language])
        return _absolute_module_files(index, path)

    def paths(
        self, source: ParsedFile, name: str, files: list[ParsedFile]
    ) -> list[ParsedFile]:
        dots = len(name) - len(name.lstrip("."))
        module = name[dots:].replace(".", "/")
        if dots:
            base = source.source.absolute_path.parent
            for _ in range(dots - 1):
                base = base.parent
            base = (base / module).resolve()
            return [
                f
                for f in files
                if f.source.absolute_path.resolve() == base.with_suffix(".py")
                or f.source.absolute_path.resolve() == base / "__init__.py"
            ]
        paths = {module + ".py", module + "/__init__.py"}
        return [f for f in files if f.source.path in paths]

    def lexical_imports(self, syntax) -> list[tuple[str, Node]]:
        result = []
        for node in syntax.nodes:
            if node.type not in self.import_nodes:
                continue
            result.extend(self._lexical_import_names(syntax, node))
        return result

    def _lexical_import_names(self, syntax, node):
        return [
            (
                text(alias) if (alias := field(child, "alias")) else text(child).split(".")[0],
                syntax.scope(node),
            )
            for child in node.children_by_field_name("name")
        ]

    def binding(self, syntax, node: Node, scope: Node):
        if node.type in {"function_definition", "class_definition"}:
            return field(node, "name"), scope
        if node.type in {"except_clause", "as_pattern"}:
            return field(node, "alias", "parameter"), scope
        target, scope = super().binding(syntax, node, scope)
        if node.type == "named_expression":
            while scope.type in COMPREHENSIONS:
                scope = syntax.scope(scope)
        return target, scope

    def visible(self, syntax, scope: Node, position: int) -> bool:
        if scope.type in COMPREHENSIONS:
            if _in_comprehension_iterable(scope, position):
                return False
        if scope.type != "class_definition" or syntax.root is None:
            return True
        return self._class_visible(syntax, scope, position)

    def _class_visible(self, syntax, scope: Node, position: int) -> bool:
        body = field(scope, "body")
        if body is not None and not body.start_byte <= position < body.end_byte:
            return False
        parent = syntax.root.descendant_for_byte_range(position, position)
        while parent and parent != scope:
            if _hides_class_scope(syntax, parent, position):
                return False
            parent = parent.parent
        return True

    def declaration_allowed(self, syntax, name: str, node: Node, position: int) -> bool:
        return node.type == "class_definition" and not any(
            alias == name and syntax._visible(scope, position)
            for alias, scope in syntax.imports
        )

    def import_shadowed(self, syntax, name: str, position: int) -> bool:
        return any(
            alias == name
            and scope.type == "class_definition"
            and (body := field(scope, "body")) is not None
            and body.start_byte <= position < body.end_byte
            and not syntax._visible(scope, position)
            for alias, scope in syntax.imports
        )

    def static(self, syntax, symbol: Symbol) -> bool:
        node = syntax.node(symbol.start_byte, symbol.end_byte)
        if node and node.parent and node.parent.type == "decorated_definition":
            return any(
                text(c).strip() in {"@staticmethod", "@classmethod"}
                for c in node.parent.named_children
                if c.type == "decorator"
            )
        return super().static(syntax, symbol)

    def import_targets(self, ctx, file, source, position):
        path = self.import_path(source)
        node = _import_node(ctx, file, position)
        if node is None:
            return super().import_targets(ctx, file, source, position)
        if node.type == "import_statement":
            return [
                (name, path_target_key(ctx.files(file, name)))
                for name, _ in _import_names(node)
            ]
        result = [
            self._from_import_target(ctx, file, source, path, name, position)
            for name, _ in _import_names(node)
        ]
        return list(dict.fromkeys(result)) or super().import_targets(ctx, file, source, position)

    def _from_import_target(self, ctx, file, source, path, name, position):
        members = ctx._members(file, path, name)
        child_path = _child_path(path, name)
        child_files = _child_module_files(ctx, file, path, name, position)
        if _bare_relative_import(source, path):
            target = members[0].key if len(members) == 1 else path_target_key(child_files)
            return child_path, target
        if child_files:
            return child_path, path_target_key(child_files)
        return path, self.import_key(ctx, file, source, position)

    def import_item(
        self, ctx, file: ParsedFile, source: str, path: str, position: int | None
    ):
        node = _import_node(ctx, file, position)
        if node is None:
            return []
        if node.type == "import_from_statement":
            return [
                self._from_import_item(ctx, file, path, name, alias, position)
                for name, alias in _import_names(node)
            ]
        return [
            (alias or name, self._module_symbols(ctx, file, name), True)
            for name, alias in _import_names(node)
        ]

    def _from_import_item(self, ctx, file, path, name, alias, position) -> tuple[str, list[Symbol], bool]:
        members = ctx._members(file, path, name)
        if members:
            return alias or name, members, False
        child_path = _child_path(path, name)
        if not _child_module_files(ctx, file, path, name, position):
            return alias or name, [], False
        return alias or name, self._module_symbols(ctx, file, child_path), True

    def _module_symbols(self, ctx, file, path) -> list[Symbol]:
        symbols = []
        for module in ctx.files(file, path):
            symbols.extend(top_symbols(module))
        return symbols

    def implicit_receiver(self, resolver, file, qualifier, call, ancestors, method):
        if qualifier != "self":
            return True
        syntax = resolver.syntax[file.source.path]
        node = syntax.node(method.start_byte, method.end_byte)
        parameters = field(node, "parameters") if node else None
        if not _self_parameter(parameters):
            return False
        return not any(
            name == "self"
            and scope.start_byte <= call.start_byte < scope.end_byte
            and declaration != parameters
            for name, scope, declaration in syntax.bindings
        )
