"""Rust extraction, metrics and resolution policies."""

import ast
import re
from collections.abc import Iterator
from dataclasses import replace
from itertools import chain
from pathlib import Path
from tree_sitter import Node
from tree_sitter_language_pack import get_parser
from ..domain.models import ParsedFile, ParsedRepository, Symbol
from ..extraction.syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    call_target,
    InheritancePolicy,
    field,
    modifier_metadata,
    text,
    walk,
)
from .resolution import ResolutionAdapter, Binding
from .resolution_paths import quoted_path
from ..extraction.resolution_syntax import SCOPES
from .base import COMMON_METRICS, LanguageAdapter
from .module_index import ModuleIndex, ModuleScope as RustScope
from .parameters import parameter_children, parameter_node

QUERY = """
(closure_expression) @definition.function
(function_signature_item name: (identifier) @name) @definition.function
"""
CALLBACK_TYPES = frozenset({"closure_expression"})
CALL_TYPES = frozenset({"call_expression", "macro_invocation"})
IMPORT_NODE = "mod_item"
INHERITANCE = InheritancePolicy(frozenset())


def declaration(node: Node) -> DeclarationCarrier:
    if node.type == "closure_expression":
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(node, frozenset({"pub"}))


def rust_module_import(node: Node) -> bool:
    """Only external module declarations are source dependencies, not inline bodies."""
    return field(node, "body") is None


def rust_call_target(site: CallSite) -> CallTarget:
    node, _, opaque, parents = site
    if node.type == "macro_invocation":
        return text(field(node, "macro")) + "!", False, None
    name, bare_target, qualifier = call_target(node)
    if not name:
        return name, bare_target, qualifier
    target = (qualifier or name).split("::")[0].split(".")[0]
    if opaque and not payload_unshadowed(node, target, parents):
        return name, False, None
    return name, bare_target, qualifier


def rust_call_sites(
    root: Node,
    offset: int = 0,
    opaque: bool = False,
    origin: Node | None = None,
    parents: tuple[Node, ...] = (),
) -> Iterator[CallSite]:
    origin = origin if origin is not None else root
    for node in walk(root):
        if node.type == "macro_invocation":
            yield node, offset, opaque, parents
            yield from _macro_sites(node, root, origin, parents, offset, opaque)
            continue
        if node.type in CALL_TYPES:
            yield node, offset, opaque, parents


def _macro_sites(
    node: Node,
    root: Node,
    origin: Node,
    parents: tuple[Node, ...],
    offset: int,
    opaque: bool,
) -> Iterator[CallSite]:
    for payload, shift in macro_payloads(node, origin, parents):
        enclosing = (root, *parents) if opaque else parents
        yield from rust_call_sites(payload, offset + shift, True, origin, enclosing)


def match_decision(node: Node) -> bool:
    pattern = node.child_by_field_name("pattern")
    return pattern is None or (pattern.text or b"").strip() != b"_"


def _path_value(value: Node) -> str | None:
    if value.type == "raw_string_literal":
        return text(
            next((c for c in value.named_children if c.type == "string_content"), None)
        )
    try:
        decoded = ast.literal_eval(text(value))
    except (SyntaxError, ValueError):
        return None
    return decoded if isinstance(decoded, str) else None


def _path_attribute(node: Node) -> str | None:
    attribute = node.named_children[0]
    value = field(attribute, "value")
    if text(attribute.named_children[0]) != "path" or value is None:
        return None
    return _path_value(value)


def path_attributes(node: Node) -> list[str]:
    """Read direct path attributes, not cfg_attr guesses; skip unrelated attributes."""
    values = []
    sibling = node.prev_named_sibling
    while sibling and sibling.type in {
        "attribute_item",
        "line_comment",
        "block_comment",
    }:
        if sibling.type == "attribute_item":
            decoded = _path_attribute(sibling)
            if decoded is not None:
                values.append(decoded)
        sibling = sibling.prev_named_sibling
    return values


def _relative_identity(identity: str, name: str) -> str | None:
    parts = identity.split("::")
    suffix = name.split("::")
    if suffix and suffix[0] == "self":
        suffix = suffix[1:]
    while suffix and suffix[0] == "super":
        parts = parts[:-1]
        suffix = suffix[1:]
    return "::".join(parts + suffix) if parts else None


def _entry_files(files: list[ParsedFile]) -> list[ParsedFile]:
    return [
        file
        for file in files
        if file.source.absolute_path.name in {"lib.rs", "main.rs"}
    ]


def _inline_scopes(
    scope: RustScope,
    identity: str,
    body: Node,
    attribute_dir: Path,
    paths: list[str],
    name: str,
) -> list[RustScope]:
    directories = (
        [attribute_dir / path for path in paths] if paths else [scope.directory / name]
    )
    return [
        RustScope(scope.file, identity, body, directory) for directory in directories
    ]


class RustModules(ModuleIndex):
    """Index explicit Rust module identities; duplicate names remain ambiguous."""

    def __init__(self, repository: ParsedRepository, syntax: dict):
        super().__init__()
        self.repository = repository
        self.syntax = syntax
        self._rust_paths: dict[Path, list[ParsedFile]] = {}
        for file in repository.files:
            if file.source.language == "rust":
                self._rust_paths.setdefault(
                    file.source.absolute_path.resolve(), []
                ).append(file)
        self.add_scopes(chain.from_iterable(map(self._walk_rust, self._rust_roots())))

    def _rust_roots(self) -> list[ParsedFile]:
        """Prefer standard entry files; otherwise infer unreferenced module owners."""
        files = self._rust_files()
        standard = _entry_files(files)
        if standard:
            return standard
        candidates = [file for file in files if self._module_owner(file)]
        referenced: set[str] = set()
        for root in candidates:
            referenced.update(self._referenced_files(root))
        return [file for file in candidates if file.source.path not in referenced]

    def _rust_files(self) -> list[ParsedFile]:
        return [
            file for file in self.repository.files if file.source.language == "rust"
        ]

    def _module_owner(self, file: ParsedFile) -> bool:
        root = self.syntax[file.source.path].root
        return bool(
            root and any(node.type == "mod_item" for node in root.named_children)
        )

    def _referenced_files(self, root: ParsedFile) -> set[str]:
        return {
            scope.file.source.path
            for scope in self._walk_rust(root)
            if scope.file.source.path != root.source.path
        }

    @staticmethod
    def _module_directory(file: ParsedFile) -> Path:
        path = file.source.absolute_path
        return path.parent if path.name == "mod.rs" else path.with_suffix("")

    def _child_scopes(self, scope: RustScope, node: Node) -> list[RustScope]:
        name = text(field(node, "name"))
        identity = scope.identity + "::" + name
        paths = path_attributes(node)
        attribute_dir = (
            scope.file.source.absolute_path.parent
            if scope.body.type == "source_file"
            else scope.directory
        )
        body = field(node, "body")
        if body:
            return _inline_scopes(scope, identity, body, attribute_dir, paths, name)
        locations = (
            [attribute_dir / path for path in paths]
            if paths
            else [scope.directory / (name + ".rs"), scope.directory / name / "mod.rs"]
        )
        return self._external_scopes(identity, locations)

    def _external_scopes(self, identity: str, locations: list[Path]) -> list[RustScope]:
        targets = chain.from_iterable(
            self._rust_paths.get(path.resolve(), []) for path in locations
        )
        return [
            RustScope(file, identity, root, self._module_directory(file))
            for file in targets
            if (root := self.syntax[file.source.path].root)
        ]

    def _walk_rust(self, root: ParsedFile):
        body = self.syntax[root.source.path].root
        if body is None:
            return
        scope = RustScope(root, "crate", body, root.source.absolute_path.parent)
        yield from self.walk_scopes(scope, self._module_children)

    def _module_children(self, scope: RustScope):
        nodes = [node for node in scope.body.named_children if node.type == "mod_item"]
        return chain.from_iterable(self._child_scopes(scope, node) for node in nodes)

    def _rust_identities(
        self, source: ParsedFile, name: str, position: int | None
    ) -> list[str]:
        if name == "crate" or name.startswith("crate::"):
            return [name]
        scopes = self.scopes_at(source, position)
        identities = [_relative_identity(scope.identity, name) for scope in scopes]
        return list(
            dict.fromkeys(identity for identity in identities if identity is not None)
        )

    def _rust_target(
        self, source: ParsedFile, name: str, position: int | None
    ) -> RustScope | None:
        # A file mounted at multiple identities has no single relative module context.
        return self.unique_scope(self._rust_identities(source, name, position))

    def rust_key(
        self, source: ParsedFile, name: str, position: int | None = None
    ) -> str | None:
        return self.scope_key(self._rust_target(source, name, position))

    def rust_import(
        self, source: ParsedFile, name: str, position: int | None = None
    ) -> list[ParsedFile]:
        """External module files. Pass a byte position for inline-relative paths.

        Inline modules cannot be represented as whole files: use rust_symbols for
        scoped namespace/member bindings rather than top_symbols(rust_import(...)).
        """
        scope = self._rust_target(source, name, position)
        return [scope.file] if scope and scope.body.type == "source_file" else []

    def rust_symbols(
        self, source: ParsedFile, name: str, position: int | None = None
    ) -> list[Symbol]:
        """Direct declarations of exactly one module, including inline namespaces."""
        return self.scope_symbols(self._rust_target(source, name, position))

    def rust_files(self, name: str) -> list[ParsedFile]:
        return self.scope_files(name)


class RustResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        match = re.search(r"\b(?:use|mod)\s+([\w:]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "rust"
    scopes = SCOPES | {"declaration_list"}
    import_nodes = {"use_declaration", "mod_item"}
    require_import_node = True
    assignments = {"assignment_expression"}
    declarations = {"let_declaration"}
    member_nodes = {"field_expression": (("value",), ("field",))}
    macro_nodes = {"macro_invocation"}
    static_nodes = {"static"}
    static_containers = {"storage_class_specifier", "modifiers"}

    def module_index(self, repository, syntax) -> RustModules:
        return RustModules(repository, syntax)

    def index(self, ctx) -> RustModules:
        return ctx.modules.indexes[self.family]

    def import_files(self, ctx, file, path, position):
        return self.index(ctx).rust_import(file, path, position)

    def import_key(self, ctx, file, source, position):
        path = self.import_path(source)
        key = self.index(ctx).rust_key(file, path, position)
        if not key and "::" in path:
            module, _, name = path.rpartition("::")
            targets = ctx._members(file, module, name, position)
            return targets[0].key if len(targets) == 1 else None
        return key

    def members(self, ctx, file, path, name, position):
        return [
            s
            for s in self.index(ctx).rust_symbols(file, path, position)
            if s.name == name
        ]

    def import_item(self, ctx, file, source, path, position):
        match = re.search(r"\buse\s+([\w:]+)(?:\s+as\s+(\w+))?", source)
        if not match:
            return []
        path, alias = match.groups()
        if self.index(ctx).rust_key(file, path, position):
            return [
                (
                    alias or path.rsplit("::", 1)[-1],
                    self.index(ctx).rust_symbols(file, path, position),
                    True,
                )
            ]
        module, _, name = path.rpartition("::")
        return [(alias or name, ctx._members(file, module, name, position), False)]

    def module_bindings(self, ctx, file, syntax, source_length):
        result = []
        for node in syntax.nodes:
            if node.type != "mod_item":
                continue
            name = text(field(node, "name"))
            result.append(
                Binding(
                    name,
                    self.index(ctx).rust_symbols(file, name, node.start_byte),
                    True,
                    node.parent.start_byte if node.parent else 0,
                    node.parent.end_byte if node.parent else source_length,
                )
            )
        return result

    def local_namespace(self, resolver, local):
        return bool(local) and all(
            (n := resolver.syntax[s.file_path].node(s.start_byte, s.end_byte))
            is not None
            and n.type == "mod_item"
            for s in local
        )

    def qualified(self, resolver, file, qualifier, name, call):
        return [
            s
            for s in self.index(resolver).rust_symbols(file, qualifier, call.start_byte)
            if s.name == name
        ]

    def receiver_rejected(self, receiver, qualifier):
        return (
            receiver is not None
            and qualifier != "this"
            and bool(re.fullmatch(r"[\w:]+", qualifier or ""))
        )


EXPRESSION_MACROS = {
    "println", "print", "eprintln", "eprint", "format", "format_args", "write",
    "writeln", "dbg", "assert", "assert_eq", "assert_ne", "debug_assert",
    "debug_assert_eq", "debug_assert_ne", "vec", "panic",
}


def _root(node: Node) -> Node:
    while node.parent is not None:
        node = node.parent
    return node


def _qualified_macro_shadowed(declaration: Node, namespace: str) -> bool:
    if declaration.type == "mod_item" and text(field(declaration, "name")) == namespace:
        return True
    return bool(
        declaration.type in {"use_declaration", "extern_crate_declaration"}
        and re.search(rf"\b{re.escape(namespace)}\b", text(declaration))
        and not text(declaration).startswith(
            (f"use {namespace}::", f"extern crate {namespace};")
        )
    )


def _macro_shadowed(declaration: Node, parts: list[str], name: str) -> bool:
    if len(parts) > 1:
        return _qualified_macro_shadowed(declaration, parts[0])
    return bool(
        declaration.type == "macro_definition"
        and text(field(declaration, "name")) == name
        or declaration.type == "use_declaration"
        and (name in text(declaration) or "*" in text(declaration))
        and not text(declaration).startswith(("use std::", "use core::"))
    )


def _walk_roots(roots):
    return chain.from_iterable(walk(root) for root in roots)


def _evaluating(node: Node, origin: Node | None, parents: tuple[Node, ...]) -> bool:
    parts = text(field(node, "macro")).split("::")
    name = parts[-1]
    if (
        name not in EXPRESSION_MACROS
        or len(parts) > 1
        and parts[0] not in {"std", "core"}
    ):
        return False
    root = _root(node)
    roots = [root, *parents]
    if origin is not None and origin.id != root.id:
        roots.append(origin)
    return not any(
        _macro_shadowed(declaration, parts, name) for declaration in _walk_roots(roots)
    )


def _macro_tokens(node: Node) -> Node | None:
    tokens = next(
        (child for child in node.named_children if child.type == "token_tree"), None
    )
    return tokens if tokens is not None and len(tokens.text or b"") >= 2 else None


def macro_payloads(
    node: Node, origin: Node | None = None, parents: tuple[Node, ...] = ()
) -> Iterator[tuple[Node, int]]:
    """Only recognized evaluating macros expose candidate calls in valid Rust syntax."""
    if not _evaluating(node, origin, parents):
        return
    tokens = _macro_tokens(node)
    if tokens is None:
        return
    for prefix, suffix in (
        (b"fn __macro_arguments(){ [", b"]; }"),
        (b"fn __macro_arguments(){ ", b" }"),
    ):
        root = (
            get_parser("rust")
            .parse(prefix + (tokens.text or b"")[1:-1] + suffix)
            .root_node
        )
        if not root.has_error:
            yield root, tokens.start_byte + 1 - len(prefix)
            return


def _pattern_names(node: Node) -> set[str]:
    if node.type in {"identifier", "field_identifier"}:
        return {text(node)}
    return set().union(
        *(
            _pattern_names(child)
            for index, child in enumerate(node.children)
            if child.is_named
            and node.field_name_for_child(index) not in {"type", "path"}
        )
    )


def _named_binding(declaration: Node, name: str) -> bool:
    return (
        declaration.type
        in {
            "function_item", "mod_item", "struct_item", "enum_item", "const_item",
            "static_item",
        }
        and text(field(declaration, "name")) == name
    )


def _payload_binding(declaration: Node, name: str) -> bool:
    pattern = None
    if declaration.type in {"let_declaration", "for_expression", "match_arm"}:
        pattern = field(declaration, "pattern")
    if declaration.type in {"parameters", "closure_parameters"}:
        pattern = declaration
    if declaration.type == "use_declaration" and (
        re.search(rf"\b{re.escape(name)}\b", text(declaration))
        or "*" in text(declaration)
    ):
        return True
    if _named_binding(declaration, name):
        return True
    return pattern is not None and name in _pattern_names(pattern)


def _payload_target(node: Node) -> Node | None:
    target = field(node, "function")
    while target is not None and target.type == "generic_function":
        target = field(target, "function") or next(iter(target.named_children), None)
    return target


def payload_unshadowed(node: Node, name: str, parents: tuple[Node, ...] = ()) -> bool:
    """Reject matching bindings in synthetic payloads without inferring local targets."""
    target = _payload_target(node)
    if target is not None and target.type == "field_expression":
        return False  # A synthetic object receiver is not a module namespace.
    return not any(
        _payload_binding(declaration, name)
        for declaration in _walk_roots((_root(node), *parents))
    )


def parameter_count(node: Node) -> int | None:
    parameters = parameter_node(node)
    if parameters is None or parameters.has_error:
        return None
    return sum(
        child.type not in {"self_parameter", "attribute_item"}
        and (field(child, "pattern") or child).type != "self"
        for child in parameter_children(parameters)
    )


METRICS = replace(COMMON_METRICS, decision_overrides={"match_arm": match_decision})
ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=rust_call_sites,
    import_node=IMPORT_NODE,
    inheritance_policy=INHERITANCE,
    normalize_call=rust_call_target,
    accept_import=rust_module_import,
    metadata=metadata,
    metrics=METRICS,
    parameter_count=parameter_count,
)
