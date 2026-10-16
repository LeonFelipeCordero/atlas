"""Rust metric and resolution policies."""

import ast

import re


from dataclasses import replace

from itertools import chain

from pathlib import Path

from tree_sitter import Node

from ..receiver_syntax import rust_bindings, type_name


from ...domain.models import Call, ParsedFile, ParsedRepository, Symbol

from .resolution import ResolutionAdapter, Binding

from .resolution_paths import quoted_path

from ..resolution_contract import SCOPES, ImportRequest, ResolutionRequest

from .base import COMMON_METRICS, MetricAdapter

from .module_index import ModuleIndex, ModuleScope as RustScope

from .parameters import parameter_children, parameter_node

from ...syntax import field, text


def match_decision(node: Node) -> bool:
    """Count a match arm unless its pattern text is exactly the wildcard _."""
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


def _inline_scopes(scope: RustScope, attribute_dir: Path, paths: list[str]) -> list[RustScope]:
    name = scope.identity.rsplit("::", 1)[-1]
    directories = [attribute_dir / path for path in paths] if paths else [scope.directory / name]
    return [replace(scope, directory=directory) for directory in directories]


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
            return _inline_scopes(
                RustScope(scope.file, identity, body, scope.directory), attribute_dir, paths
            )
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
        """Return a unique module's file/declaration key, or None if unresolved.

        A byte position selects the context for inline-relative paths.
        """
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
        """Return direct declarations of one inline/external module, or [] if unresolved.

        position is a byte offset for resolving inline-relative module paths.
        """
        return self.scope_symbols(self._rust_target(source, name, position))

    def rust_files(self, name: str) -> list[ParsedFile]:
        """Return the file for one absolute module identity; inline/ambiguous scopes yield []."""
        return self.scope_files(name)


class RustResolution(ResolutionAdapter):
    receiver_bindings = staticmethod(rust_bindings)

    def instance_members(self, resolver, parent, name):
        """Collect direct members and methods from uniquely resolved inherent impls, not traits."""
        implementations = {s.key for s in resolver.symbols.values()
                           if s.language == "rust" and self._inherent_impl(resolver, s, parent)}
        return resolver._member_declarations(parent, name) + [
            s for s in resolver.symbols.values() if s.parent_key in implementations and s.name == name
        ]

    def import_path(self, source: str) -> str:
        """Extract a use/mod path, preferring quoted text and falling back to source."""
        match = re.search(r"\b(?:use|mod)\s+([\w:]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    def _inherent_impl(self, resolver, symbol, parent):
        if symbol.kind != "impl":
            return False
        node = resolver.syntax[symbol.file_path].node(symbol.start_byte, symbol.end_byte)
        name = type_name(field(node, "type")) if node else None
        if not name or field(node, "trait"):
            return False
        types = self._impl_types(resolver, symbol, name)
        return len(types) == 1 and types[0].key == parent.key

    def _impl_types(self, resolver, symbol, name):
        file = resolver.files[symbol.file_path]
        call = Call(symbol.file_path, name, symbol.start_byte, symbol.end_byte, symbol.start_line, "")
        request = ResolutionRequest(file, call, resolver.symbols.get(symbol.parent_key), name)
        matches = self.qualify_class(resolver, request, resolver.named(request))
        if "::" in name:
            qualifier, _, member = name.rpartition("::")
            matches = self.qualified(resolver, replace(request, name=member, qualifier=qualifier))
        return [s for s in matches if s.kind in {"struct", "enum", "type"}]

    def qualify_class(self, resolver, request, matches):
        """Let a non-namespace use binding replace matches consisting only of impl blocks."""
        # An impl declaration is not a new type and must not mask its use import.
        local = resolver.lexical(request.file, request.name, request.owner)
        binding = resolver.imports.get(request.file, request.name, request.call.start_byte)
        if binding and not binding.namespace and all(s.kind == "impl" for s in local + matches):
            return binding.targets
        return matches

    def receiver_owner(self, resolver, request):
        """Resolve the enclosing impl type for a self-taking function; otherwise return []."""
        ancestors = resolver.ancestors(request.owner)
        method = self._ancestor(ancestors, "function")
        owner = self._ancestor(ancestors, "impl")
        if method is None or owner is None:
            return []
        if not self._has_self(resolver, method):
            return []
        node = resolver.syntax[owner.file_path].node(owner.start_byte, owner.end_byte)
        name = type_name(field(node, "type")) if node else None
        return self._impl_types(resolver, owner, name) if name else []

    def _ancestor(self, ancestors, kind):
        return next((s for s in ancestors if s.kind == kind), None)

    def _has_self(self, resolver, method):
        syntax = resolver.syntax[method.file_path]
        node = syntax.node(method.start_byte, method.end_byte)
        return bool(node and self._has_self_node(node))

    def static(self, syntax, symbol):
        """Treat impl functions without self as static; use shared checks for other symbols."""
        node = syntax.node(symbol.start_byte, symbol.end_byte)
        if node and node.type == "function_item" and node.parent and node.parent.type == "declaration_list":
            owner = node.parent.parent
            if owner and owner.type == "impl_item":
                return not self._has_self_node(node)
        return super().static(syntax, symbol)

    def _has_self_node(self, node):
        parameters = field(node, "parameters")
        return bool(parameters and any(
            c.type == "self_parameter" or (field(c, "pattern") or c).type == "self"
            for c in parameters.named_children
        ))

    def call_target(self, node):
        """Extract a struct literal's type name, otherwise use shared call fields."""
        if node and node.type == "struct_expression":
            return field(node, "name"), None
        return super().call_target(node)

    family = "rust"
    receiver_class_nodes = {"struct_expression"}
    self_qualifiers = {"self"}
    scopes = SCOPES | {"declaration_list"}
    import_nodes = {"use_declaration", "mod_item"}
    require_import_node = True
    assignments = {"assignment_expression", "compound_assignment_expr"}
    declarations = {"let_declaration"}
    member_nodes = {"field_expression": (("value",), ("field",))}
    macro_nodes = {"macro_invocation"}
    static_nodes = {"static"}
    static_containers = {"storage_class_specifier", "modifiers"}

    def module_index(self, repository, syntax) -> RustModules:
        """Build the explicit inline/external Rust module index for this repository."""
        return RustModules(repository, syntax)

    def index(self, ctx) -> RustModules:
        """Return the Rust module index already installed on the resolution context."""
        return ctx.modules.indexes[self.family]

    def import_files(self, ctx, request: ImportRequest):
        """Resolve one external module file at the import's optional byte position."""
        return self.index(ctx).rust_import(request.file, request.path, request.position)

    def import_key(self, ctx, request: ImportRequest):
        """Prefer a unique module key, then a unique member key for :: paths; else None."""
        file, path, position = request.file, request.path, request.position
        key = self.index(ctx).rust_key(file, path, position)
        if not key and "::" in path:
            module, _, name = path.rpartition("::")
            targets = ctx._members(replace(request, path=module), name)
            return targets[0].key if len(targets) == 1 else None
        return key

    def members(self, ctx, request: ImportRequest, name):
        """Find named direct declarations in one resolved inline or external module."""
        return [
            s
            for s in self.index(ctx).rust_symbols(request.file, request.path, request.position)
            if s.name == name
        ]

    def import_item(self, ctx, request: ImportRequest):
        """Build a simple use binding as a module namespace or imported member.

        Honor as aliases; directives without a matching use path yield [].
        """
        file, position = request.file, request.position
        match = re.search(r"\buse\s+([\w:]+)(?:\s+as\s+(\w+))?", request.source)
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
        return [(alias or name, ctx._members(replace(request, path=module), name), False)]

    def module_bindings(self, ctx, file, source_length):
        """Create namespace bindings for mod declarations within their parent byte ranges."""
        syntax = ctx.syntax[file.source.path]
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
        """Allow namespace lookup only for a nonempty set of mod declarations."""
        return bool(local) and all(
            (n := resolver.syntax[s.file_path].node(s.start_byte, s.end_byte))
            is not None
            and n.type == "mod_item"
            for s in local
        )

    def qualified(self, resolver, request):
        """Find named symbols in the qualifier's module at the call's byte position."""
        return [
            s
            for s in self.index(resolver).rust_symbols(
                request.file, request.qualifier or "", request.call.start_byte
            )
            if s.name == request.name
        ]

    def receiver_rejected(self, receiver, qualifier):
        """Reject explicit simple/path-like receivers other than this before fallback lookup."""
        return (
            receiver is not None
            and qualifier != "this"
            and bool(re.fullmatch(r"[\w:]+", qualifier or ""))
        )


def parameter_count(node: Node) -> int | None:
    """Count inputs except self and attributes; missing/error headers yield None."""
    parameters = parameter_node(node)
    if parameters is None or parameters.has_error:
        return None
    return sum(
        child.type not in {"self_parameter", "attribute_item"}
        and (field(child, "pattern") or child).type != "self"
        for child in parameter_children(parameters)
    )


METRICS = replace(COMMON_METRICS, decision_overrides={"match_arm": match_decision})


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
