"""Shared extraction policies for language adapters."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from tree_sitter import Node

from ..syntax import (
    DeclarationCarrier,
    DeclarationHeader,
    ImportPolicy,
    ParsedSyntax,
    CallSite,
    CallTarget,
    InheritancePolicy,
    DEFAULT_POLICY,
    named_carrier,
    call_sites,
    normalize_call,
    supplement_imports,
    inheritance_names,
    metadata as default_metadata,
    relationship as default_relationship,
)


@dataclass(frozen=True)
class LanguageAdapter:
    declaration_query: str = ""
    callback_types: frozenset[str] = frozenset()
    normalize_declaration: Callable[[Node], DeclarationCarrier | None] = named_carrier
    call_sites: Callable[[Node], Iterator[CallSite]] = call_sites
    import_node: str | None = None
    inheritance_policy: InheritancePolicy = DEFAULT_POLICY
    normalize_call: Callable[[CallSite], CallTarget] = normalize_call
    accept_import: Callable[[Node], bool] | None = None
    metadata: Callable[[Node], tuple[str | None, list[str]]] = default_metadata
    call_relationship: Callable[[CallSite], Literal["CALLS", "REFERENCES"]] = (
        default_relationship
    )

    def imports(
        self, syntax: ParsedSyntax, native: list[tuple[str, int]]
    ) -> list[tuple[str, int]]:
        return supplement_imports(
            syntax, native, ImportPolicy(self.import_node, self.accept_import)
        )

    def inheritance(self, header: DeclarationHeader) -> list[str]:
        return inheritance_names(header, self.inheritance_policy)
