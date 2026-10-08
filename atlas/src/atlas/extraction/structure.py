"""Merge native metadata and bundled tags on canonical syntax-tree carriers.

``extract_structure`` rebuilds source-ordered hierarchy without mutating native
items. Languages without bundled or supplemental queries retain native structure.
"""

from collections.abc import Iterator
from dataclasses import replace
from functools import lru_cache

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import (
    Span,
    StructureItem,
    get_language,
    get_parser,
    get_tags_query,
)

from ..adapters import get_adapter
from .syntax import DeclarationCarrier

DEFINITION_KINDS = {
    "definition.class": "class",
    "definition.interface": "interface",
    "definition.function": "function",
    "definition.method": "method",
    "definition.module": "module",
    "definition.struct": "struct",
    "definition.trait": "trait",
    "definition.enum": "enum",
    "definition.type": "type",
}


@lru_cache(maxsize=None)
def _declaration_query(language: str) -> Query | None:
    adapter = get_adapter(language)
    query = (get_tags_query(language) or "") + adapter.declaration_query
    return Query(get_language(language), query) if query else None


def _structure_item(
    node: Node, kind: str, name: str | None, language: str
) -> StructureItem:
    visibility, decorators = get_adapter(language).metadata(node)
    return StructureItem(
        name=name,
        kind=kind,
        signature=(node.text or b"").decode("utf-8", errors="replace"),
        visibility=visibility,
        decorators=decorators,
        span=Span(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_line=node.start_point.row,
            start_column=node.start_point.column,
            end_line=node.end_point.row,
            end_column=node.end_point.column,
        ),
    )


def _captured_declarations(
    root: Node, query: Query, language: str
) -> dict[int, tuple[Node, StructureItem]]:
    declarations: dict[int, tuple[Node, StructureItem]] = {}
    for _, captures in QueryCursor(query).matches(root):
        _add_captured_match(captures, language, declarations)
    return declarations


def _definition_capture(captures: dict[str, list[Node]]) -> str | None:
    return next((key for key in captures if key in DEFINITION_KINDS), None)


def _capture_name(nodes: list[Node]) -> str | None:
    return (nodes[0].text or b"").decode("utf-8", errors="replace") if nodes else None


def _add_captured_match(
    captures: dict[str, list[Node]],
    language: str,
    declarations: dict[int, tuple[Node, StructureItem]],
) -> None:
    definition = _definition_capture(captures)
    if definition is None:
        return
    name_nodes = captures.get("name", [])
    name = _capture_name(name_nodes)
    for node in captures[definition]:
        if node.id in declarations and not name_nodes:
            continue
        declarations[node.id] = (
            node,
            _structure_item(node, DEFINITION_KINDS[definition], name, language),
        )


def _native_declarations(
    root: Node, items: list[StructureItem]
) -> Iterator[tuple[Node, StructureItem]]:
    for item in items:
        if item.span is not None:
            node = root.descendant_for_byte_range(
                item.span.start_byte, max(item.span.start_byte, item.span.end_byte - 1)
            )
            if node is not None:
                yield node, replace(item, children=[])
        yield from _native_declarations(root, item.children)


def _canonical_declaration(
    node: Node, item: StructureItem, language: str
) -> tuple[Node, StructureItem] | None:
    carrier = get_adapter(language).normalize_declaration(node)
    if carrier is None:
        return None
    return carrier.node, _canonical_item(carrier, item, language)


def _carrier_metadata(
    carrier: DeclarationCarrier, item: StructureItem, language: str
) -> StructureItem:
    return _structure_item(
        carrier.node,
        carrier.kind or str(item.kind),
        carrier.name or item.name or None,
        language,
    )


def _span_changed(node: Node, span: Span | None) -> bool:
    return span is None or (
        span.start_byte != node.start_byte or span.end_byte != node.end_byte
    )


def _canonical_item(
    carrier: DeclarationCarrier, item: StructureItem, language: str
) -> StructureItem:
    metadata = _carrier_metadata(carrier, item, language)
    changed_span = _span_changed(carrier.node, item.span)
    return replace(
        item,
        name=metadata.name,
        kind=carrier.kind or item.kind,
        span=metadata.span if changed_span else item.span,
        signature=metadata.signature if changed_span else item.signature,
        visibility=item.visibility or metadata.visibility,
        decorators=item.decorators or list(carrier.decorators) or metadata.decorators,
        children=[],
    )


def _declaration_key(
    node: Node, item: StructureItem, language: str
) -> tuple[int, str | None]:
    # An expression has one identity, even when only native metadata names it.
    name = None if node.type in get_adapter(language).callback_types else item.name
    return node.id, name


def _merge_item(native: StructureItem, tagged: StructureItem | None) -> StructureItem:
    if tagged is None:
        return native
    return replace(
        native,
        name=native.name or tagged.name,
        kind=tagged.kind if tagged.kind == "interface" else native.kind,
        signature=native.signature or tagged.signature,
        visibility=native.visibility or tagged.visibility,
        decorators=native.decorators or tagged.decorators,
    )


def extract_structure(
    source: bytes, language: str, existing: list[StructureItem] | None = None
) -> list[StructureItem]:
    """Extract declarations under their nearest declared AST ancestor.

    Native metadata wins except AST-backed name/kind/span corrections. Identity
    is the canonical carrier (plus binding for non-callbacks), preserving
    overloads and separate clauses. No query means the
    supplied list is returned unchanged. Dependency/parser/query errors propagate.
    """
    query = _declaration_query(language)
    if query is None:
        return existing if existing is not None else []
    root = get_parser(language).parse(source).root_node
    declarations = _merge_declarations(root, query, language, existing or [])
    return _structure_hierarchy(declarations)


def _merge_declarations(
    root: Node, query: Query, language: str, existing: list[StructureItem]
) -> dict[tuple[int, str | None], tuple[Node, StructureItem]]:
    declarations: dict[tuple[int, str | None], tuple[Node, StructureItem]] = {}
    for node, item in _captured_declarations(root, query, language).values():
        declaration = _canonical_declaration(node, item, language)
        if declaration is not None:
            node, item = declaration
            declarations[_declaration_key(node, item, language)] = declaration
    for node, item in _native_declarations(root, existing):
        declaration = _canonical_declaration(node, item, language)
        if declaration is None:
            continue
        node, item = declaration
        key = _declaration_key(node, item, language)
        tagged = declarations.get(key)
        declarations[key] = (node, _merge_item(item, tagged[1] if tagged else None))
    return declarations


def _declared_parent(node: Node, by_node: dict[int, StructureItem]) -> Node | None:
    parent = node.parent
    while parent is not None and parent.id not in by_node:
        parent = parent.parent
    return parent


def _structure_hierarchy(
    declarations: dict[tuple[int, str | None], tuple[Node, StructureItem]]
) -> list[StructureItem]:
    by_node = {node.id: item for node, item in declarations.values()}
    structure = []
    for node, item in sorted(
        declarations.values(), key=lambda entry: entry[0].start_byte
    ):
        parent = _declared_parent(node, by_node)
        siblings = by_node[parent.id].children if parent is not None else structure
        siblings.append(item)
    return structure
