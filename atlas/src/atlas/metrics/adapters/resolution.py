"""Shared resolution policies, path matching and import/namespace indexes.

Policy and path helpers are re-exported here for existing adapter callers.
"""

from dataclasses import dataclass
from itertools import chain

from tree_sitter import Node

from ...domain.models import Call, ParsedFile, ParsedRepository, Symbol
from ..resolution_syntax import Syntax
from ..resolution_contract import SCOPES as SCOPES
from ..resolution_contract import ImportRequest, ResolutionRequest
from .resolution_paths import (
    import_path as import_path,
    namespace_binding as namespace_binding,
    package_targets as package_targets,
    path_target_key as path_target_key,
    relative_targets as relative_targets,
    top_symbols as top_symbols,
)
from .resolution_policy import ResolutionAdapter as ResolutionAdapter


@dataclass
class Binding:
    name: str
    targets: list[Symbol]
    namespace: bool
    start: int
    end: int
    members: dict[str, list[Symbol]] | None = None
    scope: Node | None = None

    def member(self, name: str) -> list[Symbol]:
        if self.members is not None:
            return self.members.get(name, [])
        return [symbol for symbol in self.targets if symbol.name == name]


class Modules:
    """Index fully qualified declarations; duplicate logical names stay ambiguous."""

    def __init__(self, repository: ParsedRepository, syntax: dict[str, Syntax]):
        self.repository = repository
        self.syntax = syntax
        adapters = {
            file.source.language: syntax[file.source.path].adapter
            for file in repository.files
        }
        self.indexes = {
            language: index
            for language, adapter in adapters.items()
            if (index := adapter.module_index(repository, syntax)) is not None
        }

    def declared(self, source: ParsedFile, name: str) -> list[Symbol]:
        adapter = self.syntax[source.source.path].adapter
        files = [
            file
            for file in self.repository.files
            if file.source.language == source.source.language
        ]
        return list(
            chain.from_iterable(self._declared(adapter, file, name) for file in files)
        )

    def _declared(self, adapter, file: ParsedFile, name: str) -> list[Symbol]:
        syntax = self.syntax[file.source.path]
        return [
            symbol
            for symbol in file.symbols
            if adapter.module_identity(file, symbol, syntax) == name
        ]

    def same_package(self, source: ParsedFile, name: str) -> list[Symbol]:
        return self.syntax[source.source.path].adapter.same_package(self, source, name)


class CallableIdentity:
    def __init__(self, repository: ParsedRepository, syntax: dict[str, Syntax]):
        self.syntax = syntax
        self.clauses = {}
        self.overload_indexes = {}
        adapters = {
            file.source.language: syntax[file.source.path].adapter
            for file in repository.files
        }
        for adapter in adapters.values():
            self.clauses.update(adapter.clauses(repository, syntax))

    def select(
        self, file: ParsedFile, call: Call, matches: list[Symbol]
    ) -> list[Symbol]:
        request = ResolutionRequest(file, call, None, call.name, call.qualifier)
        return self.syntax[file.source.path].adapter.select(self, request, matches)


class ImportBindings:
    """Resolve only unambiguous aliases and members within their lexical scope."""

    def __init__(
        self, repository: ParsedRepository, syntax: dict[str, Syntax], modules: Modules
    ):
        self.repository = repository
        self.syntax = syntax
        self.modules = modules
        self._paths: dict[tuple[str, str], list[ParsedFile]] = {}
        self.bindings = {
            file.source.path: self._file_bindings(file) for file in repository.files
        }

    def path_files(self, file: ParsedFile, path: str) -> list[ParsedFile]:
        key = (file.source.path, path)
        if key in self._paths:
            return self._paths[key]
        family = self.syntax[file.source.path].adapter.family or file.source.language
        files = [
            candidate
            for candidate in self.repository.files
            if (
                self.syntax[candidate.source.path].adapter.family
                or candidate.source.language
            )
            == family
        ]
        result = self.syntax[file.source.path].adapter.paths(file, path, files)
        self._paths[key] = result
        return result

    def files(
        self, file: ParsedFile, path: str, position: int | None = None
    ) -> list[ParsedFile]:
        return self.syntax[file.source.path].adapter.import_files(
            self, ImportRequest(file, path, position)
        )

    def import_key(
        self, file: ParsedFile, source: str, position: int | None = None
    ) -> str | None:
        adapter = self.syntax[file.source.path].adapter
        return adapter.import_key(self, ImportRequest(file, adapter.import_path(source), position, source))

    def _members(self, request: ImportRequest, name: str) -> list[Symbol]:
        return self.syntax[request.file.source.path].adapter.members(self, request, name)

    def _file_bindings(self, file: ParsedFile) -> list[Binding]:
        syntax = self.syntax[file.source.path]
        source_length = len(
            file.source.source.decode("utf-8", errors="replace").encode("utf-8")
        )
        result = list(
            chain.from_iterable(
                self._directive_bindings(file, item, source_length)
                for item in file.imports
            )
        )
        result.extend(syntax.adapter.module_bindings(self, file, source_length))
        return result

    def _directive_bindings(self, file, item, source_length) -> list[Binding]:
        syntax = self.syntax[file.source.path]
        adapter = syntax.adapter
        directive = syntax.import_node(item.line, item.source)
        if adapter.require_import_node and directive is None:
            return []
        scope = syntax.import_scope(item.line, item.source)
        start, end = (scope.start_byte, scope.end_byte) if scope else (0, source_length)
        position = directive.start_byte if directive is not None else None
        path = adapter.import_path(item.source)
        request = ImportRequest(file, path, position, item.source)
        entries = adapter.import_item(self, request)
        return [
            self._binding(request, Binding(name, targets, namespace, start, end, scope=scope))
            for name, targets, namespace in entries
        ]

    def _binding(self, request: ImportRequest, binding: Binding) -> Binding:
        if binding.namespace:
            binding.members = self.syntax[request.file.source.path].adapter.namespace_members(
                self, request, binding.targets
            )
        return binding

    def _visible_binding(self, syntax: Syntax, binding: Binding, position: int) -> bool:
        return (
            binding.start <= position < binding.end
            and (binding.scope is None or syntax._visible(binding.scope, position))
        )

    def _named_bindings(self, file: ParsedFile, name: str) -> list[Binding]:
        return [binding for binding in self.bindings[file.source.path] if binding.name == name]

    def get(self, file: ParsedFile, name: str, position: int) -> Binding | None:
        matches = [
            b
            for b in self._named_bindings(file, name)
            if self._visible_binding(self.syntax[file.source.path], b, position)
        ]
        if not matches:
            return None
        width = min(b.end - b.start for b in matches)
        matches = [b for b in matches if b.end - b.start == width]
        return matches[0] if len(matches) == 1 else Binding(name, [], False, 0, 0)


_import_path = import_path
_namespace_binding = namespace_binding
