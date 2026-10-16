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
    bare_instance_fields = False
    trust_receiver_annotations = True
    validate_receiver_initializer = False
    member_nodes: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    macro_nodes = frozenset()
    assignments = frozenset()
    declarations = frozenset()
    loop_bindings = frozenset()
    static_nodes = frozenset()
    static_containers = frozenset()
    member_writes = frozenset()
    receiver_updates = {"update_expression"}
    rebound_declarations = frozenset()
    single_parameter_functions = frozenset()

    def receiver_owner(self, resolver, request) -> list[Symbol] | None:
        """Return implicit receiver types; None delegates to shared inference, [] rejects."""
        return None

    @staticmethod
    def receiver_bindings(syntax, node):
        """Extract receiver declarations for a syntax node; the default provides none."""
        return []

    def instance_members(self, resolver, parent, name):
        """Return direct callable members of parent without following inheritance."""
        return resolver._member_declarations(parent, name)

    def module_index(self, repository, syntax) -> object | None:
        """Build a language-specific module index, or None when no index is needed."""
        return None

    def lexical_imports(self, syntax) -> list[tuple[str, Node]]:
        """Return imported names with lexical scope nodes; default to no shadowing entries."""
        return []

    def binding(self, syntax, node: Node, scope: Node) -> tuple[Node | None, Node]:
        """Return an assignment/declaration/loop target and its scope, or (None, scope)."""
        if node.type in self.assignments:
            return field(node, "left", "name") or next(
                iter(node.named_children), None
            ), scope
        if node.type in self.declarations:
            return field(node, "name", "declarator", "pattern"), scope
        if node.type in self.loop_bindings:
            return field(node, "left", "name"), scope
        return None, scope

    def write_target(self, node):
        """Find a write operand by field, falling back to the first named child or None."""
        return field(node, "left", "argument", "operand") or next(iter(node.named_children), None)

    def visible(self, syntax, scope: Node, position: int) -> bool:
        """Allow visibility after the caller's byte-range check; impose no extra restriction."""
        return True

    def declaration_allowed(self, syntax, lookup: DeclarationLookup) -> bool:
        """Exempt a declaration from shadowing checks; the default grants no exemption."""
        return False

    def import_shadowed(self, syntax, name: str, position: int) -> bool:
        """Report language-specific import shadowing beyond ordinary bindings; default false."""
        return False

    def is_import_node(self, node: Node) -> bool:
        """Test whether the grammar node type belongs to this policy's import nodes."""
        return node.type in self.import_nodes

    def static(self, syntax, symbol: Symbol) -> bool:
        """Detect configured static modifiers; use signature text only if syntax is absent."""
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
        """Resolve dot-prefixed slash paths relatively; otherwise use package matching."""
        if name.startswith(".") and "/" in name:
            return relative_targets(ImportRequest(source, name), files)
        return package_targets(name, files)

    def import_files(self, ctx, request: ImportRequest) -> list[ParsedFile]:
        """Resolve import files through the context's cached language-family path lookup."""
        return ctx.path_files(request.file, request.path)

    def import_path(self, source: str) -> str:
        """Extract a shared import/include path, falling back to stripped directive text."""
        return import_path(source)

    def import_key(self, ctx, request: ImportRequest) -> str | None:
        """Return a file/shared-directory key, or None for unresolved or mixed targets."""
        return path_target_key(self.import_files(ctx, request))

    def import_targets(self, ctx, request: ImportRequest) -> list[tuple[str, str | None]]:
        """Return (path, key) dependencies, retaining unresolved imports with a None key.

        Adapters may expand a directive into child-module dependencies.
        """
        return [(request.path, self.import_key(ctx, request))]

    def import_type_only(self, node: Node | None) -> bool:
        """Identify imports with no runtime dependency; default to false."""
        return False

    def import_item(self, ctx, request: ImportRequest):
        """Return (name, symbols, namespace) entries for a recognized namespace import.

        Retain an unresolved namespace with empty targets; unsupported forms yield [].
        """
        binding = namespace_binding(request.source, request.path)
        targets = self.import_files(ctx, request)
        return [(binding, _import_symbols(targets), True)] if binding else []

    def namespace_members(
        self, ctx, request: ImportRequest, targets
    ) -> dict[str, list[Symbol]] | None:
        """Provide namespace member aliases, or None to filter binding targets by name."""
        return None

    def module_bindings(self, ctx, file, source_length):
        """Return implicit module bindings outside import directives; default to none.

        source_length is the file's byte length for file-wide scope bounds.
        """
        return []

    def members(self, ctx, request: ImportRequest, name: str):
        """Find named top-level symbols only when the import resolves to one file."""
        targets = self.import_files(ctx, request)
        return (
            [s for s in top_symbols(targets[0]) if s.name == name]
            if len(targets) == 1
            else []
        )

    def module_identity(self, file: ParsedFile, symbol: Symbol, syntax) -> str:
        """Return a declaration's module-qualified lookup name; default to an empty name."""
        return ""

    def same_package(self, modules, source: ParsedFile, name: str) -> list[Symbol]:
        """Find declarations implicitly visible in source's package; default to none."""
        return []

    def qualify_class(
        self, resolver, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        """Adjust named type candidates for language qualification; default to unchanged."""
        return matches

    def qualified(self, resolver, request: ResolutionRequest) -> list[Symbol]:
        """Resolve language-specific qualified names beyond shared lookup; default to []."""
        return []

    def local_namespace(self, resolver, local: list[Symbol]) -> bool:
        """Allow local declarations to act as a namespace; default to false."""
        return False

    def static_member(self, parent: Symbol) -> bool:
        """Allow module members through static lookup without requiring a static modifier."""
        return parent.kind == "module"

    def member_overwritten(self, syntax, parent: Symbol, name: str) -> bool:
        """Reject member resolution when namespace or class bindings may replace it."""
        return syntax.member_rebound(parent.name, name) or syntax.class_rebound(
            parent, name
        )

    def call_target(self, node):
        """Return (callee, receiver) syntax nodes, using configured member fields.

        Missing syntax yields (None, None); absent callee fields use the first child.
        """
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
        """Combine target nodes with source spellings, falling back to parsed call hints."""
        return CallTarget(
            callee, receiver, text(callee) or call.name,
            text(receiver) if receiver else call.qualifier,
        )

    def receiver_type_allowed(self, syntax, name: str, member: str) -> bool:
        """Allow a receiver type only if its named member has not been rebound."""
        return not syntax.member_rebound(name, member)

    def receiver_class_allowed(self, syntax, callee, member: str) -> bool:
        """Allow class-expression member inference without extra checks by default."""
        return True

    def receiver_rejected(self, receiver, qualifier: str | None) -> bool:
        """Reject unsafe explicit receiver syntax before fallback lookup; default false."""
        return False

    def implicit_receiver(self, resolver, request: ResolutionRequest, method: Symbol) -> bool:
        """Allow a containing method's implicit receiver at the call site by default."""
        return True

    def clauses(self, repository, syntax):
        """Build callable-clause metadata keyed by symbol key; default to an empty map."""
        return {}

    def select(
        self, identity, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        """Accept only an already unique callable candidate; ambiguity yields []."""
        return matches if len(matches) == 1 else []

    def inheritance(
        self, resolver, request: ResolutionRequest, matches: list[Symbol]
    ) -> list[Symbol]:
        """Resolve dotted import namespaces or :: class names, else retain candidates."""
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
