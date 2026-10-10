"""Language-resolution policy contract, independent of the syntax cache."""

from tree_sitter import Node

from ...domain.models import ParsedFile, Symbol
from ..resolution_contract import (
    SCOPES, CallTarget, DeclarationLookup, ImportRequest, ResolutionRequest,
)
from ...syntax import field, text
from .resolution_paths import (
    import_path,
    namespace_binding,
    package_targets,
    path_target_key,
    relative_targets,
    top_symbols,
)


class ResolutionAdapter:
    family = ""
    scopes = SCOPES
    import_nodes = frozenset()
    skip_type_scope = False
    require_import_node = False
    self_qualifiers = frozenset()
    constructors = frozenset()
    receiver_class_nodes = frozenset()
    receiver_names = frozenset()
    member_nodes: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    macro_nodes = frozenset()
    assignments = frozenset()
    declarations = frozenset()
    loop_bindings = frozenset()
    static_nodes = frozenset()
    static_containers = frozenset()
    member_writes = frozenset()
    rebound_declarations = frozenset()
    single_parameter_functions = frozenset()

    def module_index(self, repository, syntax) -> object | None:
        return None

    def lexical_imports(self, syntax) -> list[tuple[str, Node]]:
        return []

    def binding(self, syntax, node: Node, scope: Node) -> tuple[Node | None, Node]:
        if node.type in self.assignments:
            return field(node, "left", "name") or next(
                iter(node.named_children), None
            ), scope
        if node.type in self.declarations:
            return field(node, "name", "declarator", "pattern"), scope
        if node.type in self.loop_bindings:
            return field(node, "left", "name"), scope
        return None, scope

    def visible(self, syntax, scope: Node, position: int) -> bool:
        return True

    def declaration_allowed(self, syntax, lookup: DeclarationLookup) -> bool:
        return False

    def import_shadowed(self, syntax, name: str, position: int) -> bool:
        return False

    def is_import_node(self, node: Node) -> bool:
        return node.type in self.import_nodes

    def static(self, syntax, symbol: Symbol) -> bool:
        node = syntax.node(symbol.start_byte, symbol.end_byte)
        if node:
            return any(
                c.type in self.static_nodes
                or c.type in self.static_containers
                and "static" in text(c).split()
                for c in node.children
            )
        return "static" in (symbol.signature or "").split("(", 1)[0].split()

    def paths(
        self, source: ParsedFile, name: str, files: list[ParsedFile]
    ) -> list[ParsedFile]:
        if name.startswith(".") and "/" in name:
            return relative_targets(ImportRequest(source, name), files)
        return package_targets(name, files)

    def import_files(self, ctx, request: ImportRequest) -> list[ParsedFile]:
        return ctx.path_files(request.file, request.path)

    def import_path(self, source: str) -> str:
        return import_path(source)

    def import_key(self, ctx, request: ImportRequest) -> str | None:
        return path_target_key(self.import_files(ctx, request))

    def import_targets(self, ctx, request: ImportRequest) -> list[tuple[str, str | None]]:
        """Keep unresolved imports explicit; adapters may expand child modules."""
        return [(request.path, self.import_key(ctx, request))]

    def import_type_only(self, node: Node | None) -> bool:
        return False

    def import_item(self, ctx, request: ImportRequest):
        binding = namespace_binding(request.source, request.path)
        targets = self.import_files(ctx, request)
        return [(binding, _import_symbols(targets), True)] if binding else []

    def namespace_members(
        self, ctx, request: ImportRequest, targets
    ) -> dict[str, list[Symbol]] | None:
        return None

    def module_bindings(self, ctx, file, source_length):
        return []

    def members(self, ctx, request: ImportRequest, name: str):
        targets = self.import_files(ctx, request)
        return (
            [s for s in top_symbols(targets[0]) if s.name == name]
            if len(targets) == 1
            else []
        )

    def module_identity(self, file: ParsedFile, symbol: Symbol, syntax) -> str:
        return ""

    def same_package(self, modules, source: ParsedFile, name: str) -> list[Symbol]:
        return []

    def qualify_class(
        self, resolver, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        return matches

    def qualified(self, resolver, request: ResolutionRequest) -> list[Symbol]:
        return []

    def local_namespace(self, resolver, local: list[Symbol]) -> bool:
        return False

    def static_member(self, parent: Symbol) -> bool:
        return parent.kind == "module"

    def member_overwritten(self, syntax, parent: Symbol, name: str) -> bool:
        return syntax.member_rebound(parent.name, name) or syntax.class_rebound(
            parent, name
        )

    def call_target(self, node):
        if node is None:
            return None, None
        callee = field(node, "function", "callee", "target", "name", "method")
        callee = callee or (node.named_children[0] if node.named_children else None)
        receiver = field(node, "object", "receiver")
        member = node if node.type in self.member_nodes else callee
        if member and member.type in self.member_nodes:
            receiver_fields, callee_fields = self.member_nodes[member.type]
            receiver = field(member, *receiver_fields)
            callee = field(member, *callee_fields)
        return callee, receiver

    def normalized_call(self, call, callee, receiver) -> CallTarget:
        return CallTarget(
            callee, receiver, text(callee) or call.name,
            text(receiver) if receiver else call.qualifier,
        )

    def receiver_class_allowed(self, syntax, callee, member: str) -> bool:
        return True

    def receiver_rejected(self, receiver, qualifier: str | None) -> bool:
        return False

    def implicit_receiver(self, resolver, request: ResolutionRequest, method: Symbol) -> bool:
        return True

    def clauses(self, repository, syntax):
        return {}

    def select(
        self, identity, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        return matches if len(matches) == 1 else []

    def inheritance(
        self, resolver, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        if "." in request.name:
            inherited = _namespace_inheritance(resolver, request)
            if inherited is not None:
                return inherited
        if "::" in request.name:
            return resolver.class_named(request)
        return matches


def _namespace_inheritance(resolver, request: ResolutionRequest) -> list[Symbol] | None:
    qualifier, _, terminal = request.name.rpartition(".")
    binding = resolver.imports.get(request.file, qualifier, request.call.start_byte)
    if binding and binding.namespace and _inheritance_namespace(resolver, request, qualifier):
        return [symbol for symbol in binding.targets if symbol.name == terminal]
    return None


def _inheritance_namespace(resolver, request: ResolutionRequest, qualifier: str) -> bool:
    return (
        not resolver.lexical(request.file, qualifier, request.owner)
        and not resolver.syntax[request.file.source.path].shadowed(qualifier, request.call.start_byte)
    )


def _import_symbols(files: list[ParsedFile]) -> list[Symbol]:
    from itertools import chain

    return list(chain.from_iterable(top_symbols(file) for file in files))
