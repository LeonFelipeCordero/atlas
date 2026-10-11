"""Resolve parsed imports, inheritance and calls into graph connections.

Only ``resolve_connections`` is public; other functions are internal helpers.
Ambiguous or unresolved targets become deduplicated external nodes.
"""

from __future__ import annotations

import re
from typing import Callable
from dataclasses import replace
from .resolution_contract import CallTarget, ImportRequest, ResolutionRequest
from .adapters.resolution import (
    Binding,
    ImportBindings,
    CallableIdentity,
    Modules,
)
from ..syntax import text
from .resolution_syntax import IDENTIFIERS, Syntax
from .receiver_resolution import ReceiverTypes

from pydantic.dataclasses import dataclass

from .adapters import get_resolution_adapter
from ..domain.models import MODEL_CONFIG, Confidence, Relationship
from ..domain.models import (
    Call,
    Import,
    Inheritance,
    ParsedFile,
    ParsedRepository,
    Symbol,
    file_key,
)


@dataclass(config=MODEL_CONFIG)
class ExternalNode:
    """An unresolved module, type or callable identified by a stable key."""

    key: str
    language: str
    kind: str
    name: str


@dataclass(config=MODEL_CONFIG)
class Connection:
    """A directed relationship with confidence and source-location evidence."""

    source_key: str
    target_key: str
    type: Relationship
    confidence: Confidence
    path: str
    line: int
    evidence: str | None
    type_only: bool = False


@dataclass(config=MODEL_CONFIG)
class ResolvedGraph:
    """Resolved relationships and the external nodes they reference."""

    connections: list[Connection]
    external_nodes: list[ExternalNode]


def _external_key(language: str, kind: str, name: str) -> str:
    """Build the deduplication key for an external target."""
    return f"external:{language}:{kind}:{name}"


def _resolve_calls(
    repository: ParsedRepository,
    resolver: CallResolver,
    _external: Callable[[str, str, str], str],
) -> list[Connection]:
    """Emit precise semantic targets, or an external node when identity is unsafe."""
    connections = []
    for call in repository.calls:
        connections.extend(_call_connections(call, resolver, _external))
    return connections


def _call_connections(
    call: Call, resolver: CallResolver, external: Callable[[str, str, str], str]
) -> list[Connection]:
    source_file = resolver.files[call.file_path].source
    source = resolver.owner(call)
    source_key = source.key if source else file_key(call.file_path)
    matches = resolver.resolve(call, source)
    targets = [s.key for s in matches] or [
        external(source_file.language, "callable", call.name)
    ]
    return [
        Connection(
            source_key,
            target_key,
            call.relationship,
            "INFERRED",
            call.file_path,
            call.line,
            call.evidence,
        )
        for target_key in targets
    ]


def resolve_connections(repository: ParsedRepository) -> ResolvedGraph:
    """Resolve import, inheritance and call edges, retaining external targets.

    Args:
        repository: Parsed files with symbols and extracted relationships.

    Returns:
        Connections in import, inheritance, then call order, plus deduplicated
        external nodes for unresolved or ambiguous targets.

    Raises:
        KeyError: An import or call references a file path absent from repository.

    Examples:
        >>> resolve_connections(ParsedRepository(files=[]))
        ResolvedGraph(connections=[], external_nodes=[])
    """
    external_nodes: dict[str, ExternalNode] = {}
    resolver = CallResolver(repository)

    def _external(language: str, kind: str, name: str) -> str:
        """Register an external target once and return its key."""
        key = _external_key(language, kind, name)
        external_nodes.setdefault(key, ExternalNode(key, language, kind, name))
        return key

    connections = _resolve_imports(repository, resolver, _external)
    connections.extend(_resolve_inheritances(repository, resolver, _external))
    connections.extend(_resolve_calls(repository, resolver, _external))
    return ResolvedGraph(connections, list(external_nodes.values()))


def _resolve_imports(
    repository: ParsedRepository,
    resolver: CallResolver,
    external: Callable[[str, str, str], str],
) -> list[Connection]:
    connections = []
    for item in repository.imports:
        connections.extend(_import_connections(item, resolver, external))
    return connections


def _import_connections(
    item: Import,
    resolver: CallResolver,
    external: Callable[[str, str, str], str],
) -> list[Connection]:
    file = resolver.files[item.file_path]
    directive = resolver.syntax[item.file_path].import_node(item.line, item.source)
    position = directive.start_byte if directive is not None else None
    adapter = get_resolution_adapter(file.source.language)
    request = ImportRequest(file, adapter.import_path(item.source), position, item.source)
    targets = adapter.import_targets(resolver.imports, request)
    if adapter.require_import_node and directive is None:
        targets = [(adapter.import_path(item.source), None)]
    return [
        Connection(
            file_key(item.file_path),
            target_key or external(file.source.language, "module", name),
            "IMPORTS",
            "INFERRED" if target_key else "EXTRACTED",
            item.file_path,
            item.line,
            item.source,
            type_only=adapter.import_type_only(directive),
        )
        for name, target_key in targets
    ]


def _resolve_inheritances(
    repository: ParsedRepository,
    resolver: CallResolver,
    external: Callable[[str, str, str], str],
) -> list[Connection]:
    connections = []
    for inheritance in repository.inheritances:
        matches = _inheritance_targets(resolver, inheritance)
        target_key = (
            matches[0].key
            if len(matches) == 1
            else external(inheritance.language, "type", inheritance.target_name)
        )
        connections.append(
            Connection(
                inheritance.source_key,
                target_key,
                "INHERITS",
                "INFERRED",
                inheritance.file_path,
                inheritance.line,
                inheritance.evidence,
            )
        )
    return connections


def _inheritance_targets(
    resolver: CallResolver, inheritance: Inheritance
) -> list[Symbol]:
    """Require a visible base declaration/import rather than a global name guess."""
    file = resolver.files[inheritance.file_path]
    declaration = resolver.symbols[inheritance.source_key]
    owner = resolver.symbols.get(declaration.parent_key)
    name = inheritance.target_name
    call = Call(
        file.source.path,
        name,
        declaration.start_byte,
        declaration.end_byte,
        inheritance.line,
        inheritance.evidence,
        True,
    )
    request = ResolutionRequest(file, call, owner, name)
    matches = resolver.named(request)
    matches = get_resolution_adapter(file.source.language).inheritance(
        resolver, request, matches
    )
    return [
        symbol
        for symbol in matches
        if symbol.kind in {"class", "interface", "struct", "trait", "type"}
    ]


TYPES = {"class", "struct", "enum", "object"}
CALLABLES = {"function", "method", "constructor"} | TYPES


def _language_family(language: str) -> str:
    return get_resolution_adapter(language).family or language


def _import_masks_local(
    file: ParsedFile, binding: Binding | None, local: list[Symbol]
) -> bool:
    if binding is None:
        return False
    return (
        any(s.parent_key == file_key(file.source.path) for s in local)
        and binding.start == 0
    )


def _enclosing_method(ancestors: list[Symbol]) -> tuple[Symbol | None, Symbol | None]:
    parent = next((s for s in ancestors if s.kind in TYPES), None)
    if parent is None:
        return None, None
    method = next((s for s in ancestors if s.parent_key == parent.key), None)
    return parent, method


def _is_bare_target(call: Call, callee) -> bool:
    return bool(
        call.bare_target or callee and callee.type in IDENTIFIERS | {"type_identifier"}
    )


class CallResolver:
    """Repository-local indexes; syntax is parsed once, with no fixture-specific inference."""

    def __init__(self, repository: ParsedRepository):
        self.repository = repository
        self.files = {f.source.path: f for f in repository.files}
        self.symbols = {s.key: s for s in repository.symbols}
        self.syntax = {
            p: Syntax(f, get_resolution_adapter(f.source.language))
            for p, f in self.files.items()
        }
        self.modules = Modules(repository, self.syntax)
        self.imports = ImportBindings(repository, self.syntax, self.modules)
        self.identity = CallableIdentity(repository, self.syntax)
        self.receivers = ReceiverTypes(self)

    def owner(self, call: Call) -> Symbol | None:
        enclosing = [
            s
            for s in self.files[call.file_path].symbols
            if s.start_byte <= call.start_byte and call.end_byte <= s.end_byte
        ]
        return (
            min(enclosing, key=lambda s: s.end_byte - s.start_byte)
            if enclosing
            else None
        )

    def ancestors(self, owner: Symbol | None) -> list[Symbol]:
        result = []
        while owner and owner not in result:
            result.append(owner)
            owner = self.symbols.get(owner.parent_key)
        return result

    def lexical(
        self, file: ParsedFile, name: str, owner: Symbol | None
    ) -> list[Symbol]:
        """Nearest visible declaration wins; unrelated nested declarations aren't globals."""
        ancestors = self.ancestors(owner)
        scopes = [s.key for s in ancestors] + [file_key(file.source.path)]
        for scope in scopes:
            matches = self._scope_declarations(file, name, scope)
            if matches:
                return matches
        return []

    def _scope_declarations(
        self, file: ParsedFile, name: str, scope: str
    ) -> list[Symbol]:
        parent = self.symbols.get(scope)
        if (
            parent
            and parent.kind in TYPES
            and get_resolution_adapter(file.source.language).skip_type_scope
        ):
            return []
        return [s for s in file.symbols if s.name == name and s.parent_key == scope]

    def named(self, request: ResolutionRequest, fallback: bool = False) -> list[Symbol]:
        file, name, call = request.file, request.name, request.call
        binding = self.imports.get(file, name, call.start_byte)
        local = self.lexical(file, name, request.owner)
        if self.syntax[file.source.path].shadowed(name, call.start_byte, local):
            return []
        if local:
            return [] if _import_masks_local(file, binding, local) else local
        if binding:
            return binding.targets if not binding.namespace else []
        package = self.modules.same_package(file, name)
        if package:
            return package
        if not fallback:
            return []
        # Preserve legacy unique bare-call behavior, but never for receiver type inference.
        return self._fallback_named(file, name)

    def _fallback_named(self, file: ParsedFile, name: str) -> list[Symbol]:
        family = _language_family(file.source.language)
        return [
            s
            for s in self.repository.symbols
            if s.name == name
            and _language_family(s.language) == family
            and s.kind in CALLABLES - TYPES
        ]

    def class_named(self, request: ResolutionRequest) -> list[Symbol]:
        matches = self.named(request)
        matches = get_resolution_adapter(request.file.source.language).qualify_class(
            self, request, matches
        )
        return [s for s in matches if s.kind in TYPES]

    def _receiver_class(self, request: ResolutionRequest, receiver) -> list[Symbol]:
        if receiver is None:
            return []
        file = request.file
        adapter = get_resolution_adapter(file.source.language)
        if receiver.type not in adapter.receiver_class_nodes:
            return []
        callee, nested = adapter.call_target(receiver)
        if nested is not None:
            return []
        syntax = self.syntax[file.source.path]
        if not adapter.receiver_class_allowed(syntax, callee, request.name):
            return []
        return self.class_named(replace(request, name=text(callee)))

    def _self_class(self, request: ResolutionRequest) -> list[Symbol]:
        file = request.file
        ancestors = self.ancestors(request.owner)
        parent, method = _enclosing_method(ancestors)
        if parent is None or method is None:
            return []
        if self.syntax[file.source.path].static(method):
            return []
        if not get_resolution_adapter(file.source.language).implicit_receiver(
            self, request, method
        ):
            return []
        return [parent]

    def members(self, types: list[Symbol], name: str, static: bool) -> list[Symbol]:
        if len(types) != 1:
            return []
        parent = types[0]
        syntax = self.syntax[parent.file_path]
        if get_resolution_adapter(parent.language).member_overwritten(
            syntax, parent, name
        ):
            return []
        declarations = get_resolution_adapter(parent.language).instance_members(self, parent, name)
        if not static:
            return declarations
        return self._static_members(parent, declarations)

    def _member_declarations(self, parent: Symbol, name: str) -> list[Symbol]:
        return [
            s
            for s in self.files[parent.file_path].symbols
            if s.parent_key == parent.key and s.name == name and s.kind in CALLABLES
        ]

    def _static_members(
        self, parent: Symbol, declarations: list[Symbol]
    ) -> list[Symbol]:
        return [
            s
            for s in declarations
            if self.syntax[s.file_path].static(s)
            or get_resolution_adapter(parent.language).static_member(parent)
        ]

    def _namespace_member(self, request: ResolutionRequest, binding: Binding) -> list[Symbol]:
        file, qualifier, name = request.file, request.qualifier or "", request.name
        local = self.lexical(file, qualifier, request.owner)
        module = get_resolution_adapter(file.source.language).local_namespace(
            self, local
        )
        if local and not module:
            return self.members(
                self.class_named(replace(request, name=qualifier)), name, True
            )
        return binding.member(name)

    def qualified(self, request: ResolutionRequest) -> list[Symbol]:
        file, name, qualifier = request.file, request.name, request.qualifier or ""
        call = request.call
        if self.syntax[file.source.path].member_rebound(qualifier, name):
            return []
        if qualifier in get_resolution_adapter(file.source.language).self_qualifiers:
            return self.members(
                self._self_class(request), name, False
            )
        if self.syntax[file.source.path].shadowed(
            qualifier.split(".")[0], call.start_byte
        ):
            return []
        return self._qualified_binding(request)

    def _qualified_binding(self, request: ResolutionRequest) -> list[Symbol]:
        file, name, qualifier = request.file, request.name, request.qualifier or ""
        binding = self.imports.get(file, qualifier, request.call.start_byte)
        if binding and binding.namespace:
            return self._namespace_member(request, binding)
        types = self.class_named(replace(request, name=qualifier))
        if types:
            return self.members(types, name, True)
        if binding:
            return self.members(binding.targets, name, True)
        return get_resolution_adapter(file.source.language).qualified(
            self, request
        )

    def _bare(self, request: ResolutionRequest, node) -> list[Symbol]:
        constructor = (
            node is not None
            and node.type in get_resolution_adapter(request.file.source.language).constructors
        )
        return self.named(request, fallback=not constructor)

    def _matches(self, request: ResolutionRequest, node, target: CallTarget) -> list[Symbol]:
        file = request.file
        receiver, qualifier = target.receiver, request.qualifier
        if qualifier and not self.syntax[file.source.path].member_rebound(qualifier, request.name):
            typed = self.receivers.resolve(request)
            if typed is not None:
                return typed
        if get_resolution_adapter(file.source.language).receiver_rejected(
            receiver, qualifier
        ):
            return []
        if (
            receiver
            and receiver.type
            not in IDENTIFIERS
            | get_resolution_adapter(file.source.language).receiver_names
        ):
            return self._receiver_matches(request, receiver)
        if qualifier:
            return self.qualified(request)
        if _is_bare_target(request.call, target.callee):
            return self._bare(request, node)
        return []

    def _receiver_matches(self, request: ResolutionRequest, receiver) -> list[Symbol]:
        if re.fullmatch(r"[\w$]+(?:\.|::)[\w.$:]+", request.qualifier or ""):
            return self.qualified(request)
        return self.members(
            self._receiver_class(request, receiver), request.name, False
        )

    def resolve(self, call: Call, owner: Symbol | None) -> list[Symbol]:
        file = self.files[call.file_path]
        node = self.syntax[call.file_path].node(call.start_byte, call.end_byte)
        adapter = get_resolution_adapter(file.source.language)
        if node and node.type in adapter.macro_nodes:
            return []
        callee, receiver = adapter.call_target(node)
        target = adapter.normalized_call(call, callee, receiver)
        request = ResolutionRequest(file, call, owner, target.name, target.qualifier)
        scoped = re.fullmatch(r"([\w.:]+)(?:\.|::)([\w$!?]+)", target.name)
        if scoped and target.receiver is None:
            qualifier, name = scoped.groups()
            request = replace(request, name=name, qualifier=qualifier)
        matches = self._matches(request, node, target)
        return self.identity.select(
            file,
            call,
            [s for s in matches if s.kind in CALLABLES or s.kind == "module"],
        )
