"""Language-neutral storage, traversal and lookup for lexical module scopes."""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node

from ...domain.models import ParsedFile, Symbol, file_key
from .resolution_paths import top_symbols


@dataclass
class ModuleScope:
    file: ParsedFile
    identity: str
    body: Node
    directory: Path


class ModuleIndex:
    def __init__(self) -> None:
        self._scopes: dict[str, list[ModuleScope]] = {}
        self._file_scopes: dict[str, list[ModuleScope]] = {}

    def add_scopes(self, scopes: Iterable[ModuleScope]) -> None:
        """Append scopes to identity and file indexes without removing duplicates."""
        for scope in scopes:
            self._scopes.setdefault(scope.identity, []).append(scope)
            self._file_scopes.setdefault(scope.file.source.path, []).append(scope)

    @staticmethod
    def walk_scopes(
        root: ModuleScope, children: Callable[[ModuleScope], Iterable[ModuleScope]]
    ) -> Iterator[ModuleScope]:
        """Yield root and descendants depth-first, avoiding file-root cycles per path."""
        pending = [(root, {root.file.source.path})]
        while pending:
            scope, seen = pending.pop()
            yield scope
            pending.extend(_pending_scopes(scope, seen, children))

    def scopes_at(self, source: ParsedFile, position: int | None) -> list[ModuleScope]:
        """Return narrowest scopes containing a byte position, or file roots for None."""
        scopes = self._file_scopes.get(source.source.path, [])
        if position is None:
            return [scope for scope in scopes if scope.body.parent is None]
        scopes = [
            scope
            for scope in scopes
            if scope.body.start_byte <= position < scope.body.end_byte
        ]
        return _narrowest_scopes(scopes)

    def unique_scope(self, identities: list[str]) -> ModuleScope | None:
        """Resolve exactly one identity with exactly one indexed scope; else return None."""
        if len(identities) != 1:
            return None
        scopes = self._scopes.get(identities[0], [])
        return scopes[0] if len(scopes) == 1 else None

    @staticmethod
    def scope_key(scope: ModuleScope | None) -> str | None:
        """Return the file or enclosing declaration key, or None if unavailable."""
        if scope is None:
            return None
        if scope.body.parent is None:
            return file_key(scope.file.source.path)
        declaration = scope.body.parent
        return next(
            (
                symbol.key
                for symbol in scope.file.symbols
                if (symbol.start_byte, symbol.end_byte)
                == (declaration.start_byte, declaration.end_byte)
            ),
            None,
        )

    @staticmethod
    def scope_symbols(scope: ModuleScope | None) -> list[Symbol]:
        """Return direct declarations of a file/inline scope; return [] for None."""
        if scope is None:
            return []
        if scope.body.parent is None:
            return top_symbols(scope.file)
        spans = {(n.start_byte, n.end_byte) for n in scope.body.named_children}
        return [s for s in scope.file.symbols if (s.start_byte, s.end_byte) in spans]

    def scope_files(self, identity: str) -> list[ParsedFile]:
        """Return the unique module file; inline or ambiguous scopes yield []."""
        scope = self.unique_scope([identity])
        return [scope.file] if scope and scope.body.parent is None else []


def _pending_scopes(scope, seen, children):
    return [
        (child, seen | {child.file.source.path})
        for child in children(scope)
        if not (child.body.parent is None and child.file.source.path in seen)
    ]


def _narrowest_scopes(scopes: list[ModuleScope]) -> list[ModuleScope]:
    width = min((s.body.end_byte - s.body.start_byte for s in scopes), default=0)
    return [s for s in scopes if s.body.end_byte - s.body.start_byte == width]
