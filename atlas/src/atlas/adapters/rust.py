"""Rust extraction, metrics and resolution policies."""

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from tree_sitter import Node
from ..domain.models import ParsedFile, ParsedRepository, Symbol, file_key
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
from .resolution import ResolutionAdapter, Binding, import_path
from ..extraction.resolution_syntax import SCOPES
from .macro_evaluation import (
    EXPRESSION_MACROS as EXPRESSION_MACROS,
    macro_payloads as macro_payloads,
    payload_unshadowed as payload_unshadowed,
)

QUERY = "\n(closure_expression) @definition.function\n"
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


def top_symbols(file: ParsedFile) -> list[Symbol]:
    return [s for s in file.symbols if s.parent_key == file_key(file.source.path)]


@dataclass
class RustScope:
    """A logical module, its lexical body, and its default child-module directory."""

    file: ParsedFile
    identity: str
    body: Node
    directory: Path


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


def _narrowest_scopes(scopes: list[RustScope]) -> list[RustScope]:
    width = min(
        (scope.body.end_byte - scope.body.start_byte for scope in scopes), default=0
    )
    return [
        scope
        for scope in scopes
        if scope.body.end_byte - scope.body.start_byte == width
    ]


class RustModules:
    """Index explicit Rust module identities; duplicate names remain ambiguous."""

    def __init__(self, repository: ParsedRepository, syntax: dict):
        self.repository = repository
        self.syntax = syntax
        self._rust_scopes: dict[str, list[RustScope]] = {}
        self._file_scopes: dict[str, list[RustScope]] = {}
        self._rust_paths: dict[Path, list[ParsedFile]] = {}
        for file in repository.files:
            if file.source.language == "rust":
                self._rust_paths.setdefault(
                    file.source.absolute_path.resolve(), []
                ).append(file)
        for scope in chain.from_iterable(map(self._walk_rust, self._rust_roots())):
            self._rust_scopes.setdefault(scope.identity, []).append(scope)
            self._file_scopes.setdefault(scope.file.source.path, []).append(scope)

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
        pending = [
            (
                RustScope(root, "crate", body, root.source.absolute_path.parent),
                {root.source.path},
            )
        ]
        while pending:
            scope, seen = pending.pop()
            yield scope
            pending.extend(self._pending_children(scope, seen))

    def _module_children(self, scope: RustScope):
        nodes = [node for node in scope.body.named_children if node.type == "mod_item"]
        return chain.from_iterable(self._child_scopes(scope, node) for node in nodes)

    def _pending_children(self, scope: RustScope, seen: set[str]):
        return [
            (child, seen | {child.file.source.path})
            for child in self._module_children(scope)
            if not (child.body.type == "source_file" and child.file.source.path in seen)
        ]

    def _rust_identities(
        self, source: ParsedFile, name: str, position: int | None
    ) -> list[str]:
        if name == "crate" or name.startswith("crate::"):
            return [name]
        scopes = self._scopes_at(source, position)
        identities = [_relative_identity(scope.identity, name) for scope in scopes]
        return list(
            dict.fromkeys(identity for identity in identities if identity is not None)
        )

    def _scopes_at(self, source: ParsedFile, position: int | None) -> list[RustScope]:
        scopes = self._file_scopes.get(source.source.path, [])
        if position is None:
            return [scope for scope in scopes if scope.body.type == "source_file"]
        scopes = [
            scope
            for scope in scopes
            if scope.body.start_byte <= position < scope.body.end_byte
        ]
        return _narrowest_scopes(scopes)

    def _rust_target(
        self, source: ParsedFile, name: str, position: int | None
    ) -> RustScope | None:
        identities = self._rust_identities(source, name, position)
        # A file mounted at multiple identities has no single relative module context.
        if len(identities) != 1:
            return None
        scopes = self._rust_scopes.get(identities[0], [])
        return scopes[0] if len(scopes) == 1 else None

    def rust_key(
        self, source: ParsedFile, name: str, position: int | None = None
    ) -> str | None:
        scope = self._rust_target(source, name, position)
        if scope is None:
            return None
        if scope.body.type == "source_file":
            return file_key(scope.file.source.path)
        declaration = scope.body.parent
        return next(
            (
                symbol.key
                for symbol in scope.file.symbols
                if declaration is not None
                and (symbol.start_byte, symbol.end_byte)
                == (declaration.start_byte, declaration.end_byte)
            ),
            None,
        )

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
        scope = self._rust_target(source, name, position)
        if scope is None:
            return []
        if scope.body.type == "source_file":
            return top_symbols(scope.file)
        spans = {(n.start_byte, n.end_byte) for n in scope.body.named_children}
        return [s for s in scope.file.symbols if (s.start_byte, s.end_byte) in spans]

    def rust_files(self, name: str) -> list[ParsedFile]:
        scopes = self._rust_scopes.get(name, [])
        if len(scopes) != 1 or scopes[0].body.type != "source_file":
            return []
        return [scopes[0].file]


class RustResolution(ResolutionAdapter):
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
        path = import_path(source)
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
