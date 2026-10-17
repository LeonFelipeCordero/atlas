"""Focused structure contracts without parsing source or compiling queries."""

from copy import deepcopy
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from tree_sitter import Point
from tree_sitter_language_pack import Span, StructureItem

from atlas.parsing import structure
from atlas.parsing.syntax import DeclarationCarrier


@dataclass
class FakeNode:
    id: int
    start_byte: int = 0
    end_byte: int = 100
    type: str = "declaration"
    text: bytes = b"canonical declaration"
    parent: "FakeNode | None" = None
    start_point: Point = Point(2, 3)
    end_point: Point = Point(4, 5)
    ranges: dict = field(default_factory=dict)

    def descendant_for_byte_range(self, start, end):
        return self.ranges.get((start, end))


def Node(*args, **kwargs) -> Any:
    return FakeNode(*args, **kwargs)


def install_adapter(monkeypatch, **overrides):
    adapter = SimpleNamespace(
        metadata=lambda node: ("public", ["@ast"]),
        normalize_declaration=lambda node: DeclarationCarrier(node),
        callback_types={"callback"},
    )
    vars(adapter).update(overrides)
    monkeypatch.setattr(structure, "get_adapter", lambda language: adapter)
    return adapter


@pytest.mark.parametrize(
    "case",
    [(["@native"], ("@carrier",), ["@native"]),
     ([], ("@carrier",), ["@carrier"]), ([], (), ["@ast"])],
)
def test_canonical_metadata_precedence(monkeypatch, case):
    native_decorators, carrier_decorators, expected = case
    # Given conflicting native and canonical metadata on the same byte span.
    install_adapter(monkeypatch)
    node = Node(1)
    span = Span(0, 100, 8, 9, 10, 11)
    child = StructureItem(name="child")
    native = StructureItem(
        name="old", kind="function", span=span, signature="native signature",
        visibility="private", decorators=native_decorators, children=[child],
        doc_comment="native documentation", body_span=Span(10, 90),
    )
    before = deepcopy(native)
    carrier = DeclarationCarrier(node, "canonical", "method", carrier_decorators)

    # When canonical metadata is applied.
    result = structure._canonical_item(carrier, native, "test")

    # Then AST name/kind win, native metadata survives, and hierarchy is reset.
    assert (result.name, result.kind) == ("canonical", "method")
    assert result.span is span
    assert result.signature == "native signature"
    assert result.visibility == "private"
    assert result.decorators == expected
    assert result.doc_comment == "native documentation"
    assert result.body_span == native.body_span
    assert result.children == []
    assert native == before


@pytest.mark.parametrize("span", [None, Span(1, 100), Span(0, 99)])
def test_changed_span_replaces_signature_and_coordinates(monkeypatch, span):
    # Given a missing or stale native span and no adapter name/kind override.
    install_adapter(monkeypatch)
    node = Node(1, text=b"declaration \xff")
    native = StructureItem(name="native", kind="class", span=span, signature="stale")

    # When the canonical carrier supplies the declaration boundary.
    result = structure._canonical_item(DeclarationCarrier(node), native, "test")

    # Then byte and point coordinates, signature, and fallback metadata agree.
    assert result.span == Span(0, 100, 2, 3, 4, 5)
    assert result.signature == "declaration \ufffd"
    assert (result.name, result.kind) == ("native", "class")
    assert result.visibility == "public"
    assert result.decorators == ["@ast"]
    assert native.span == span
    assert native.signature == "stale"


@pytest.mark.parametrize(
    ("tagged_kind", "expected_kind"),
    [("interface", "interface"), ("method", "class")],
)
def test_merge_preserves_native_metadata_except_tagged_interface(
    tagged_kind, expected_kind
):
    # Given conflicting native and tagged declarations.
    native = StructureItem(
        name="native", kind="class", signature="native signature",
        visibility="private", decorators=["@native"], span=Span(1, 10),
        doc_comment="native documentation",
    )
    tagged = StructureItem(
        name="tagged", kind=tagged_kind, signature="tagged signature",
        visibility="public", decorators=["@tagged"], span=Span(0, 20),
    )
    before = deepcopy((native, tagged))

    # When both descriptions are merged.
    result = structure._merge_item(native, tagged)

    # Then only the interface exception overrides populated native metadata.
    assert result == StructureItem(
        name="native", kind=expected_kind, signature="native signature",
        visibility="private", decorators=["@native"], span=Span(1, 10),
        doc_comment="native documentation",
    )
    assert (native, tagged) == before


def test_merge_fills_missing_native_metadata():
    # Given a native declaration with only its own kind and span.
    native = StructureItem(kind="method", span=Span(1, 10))
    tagged = StructureItem(
        name="tagged", kind="function", signature="tagged signature",
        visibility="public", decorators=["@tagged"],
    )

    # When tagged metadata fills the gaps.
    result = structure._merge_item(native, tagged)

    # Then native identity metadata is retained and absent fields are filled.
    assert result == StructureItem(
        name="tagged", kind="method", span=Span(1, 10),
        signature="tagged signature", visibility="public", decorators=["@tagged"],
    )
    assert structure._merge_item(native, None) is native


@pytest.mark.parametrize("node_type", ["callback", "declaration"])
def test_merge_identity_uses_binding_except_for_callbacks(monkeypatch, node_type):
    # Given one carrier with different tag/native names and a separate overload.
    install_adapter(monkeypatch)
    node = Node(1, type=node_type)
    overload = Node(2, 100, 200, type=node_type)
    root = Node(0, ranges={(0, 99): node})
    syntax = Mock(source=SimpleNamespace(language="test"), tree=lambda: root)
    tagged = StructureItem(name="tagged", span=Span(0, 100))
    second = StructureItem(name="native", span=Span(100, 200))
    native = StructureItem(name="native", span=Span(0, 100), doc_comment="native doc")
    monkeypatch.setattr(
        structure, "_captured_declarations",
        lambda *args: {1: (node, tagged), 2: (overload, second)},
    )

    # When declarations are canonicalized and merged.
    declarations = structure._merge_declarations(syntax, Mock(), [native])

    # Then callbacks coalesce despite names, bindings and overloads stay distinct.
    if node_type == "callback":
        assert set(declarations) == {(1, None), (2, None)}
        assert declarations[(1, None)][1].name == "native"
        assert declarations[(1, None)][1].doc_comment == "native doc"
    else:
        assert set(declarations) == {(1, "tagged"), (1, "native"), (2, "native")}
        assert declarations[(1, "native")][1].doc_comment == "native doc"


def test_hierarchy_orders_siblings_under_nearest_declared_ancestor():
    # Given scrambled declarations, undeclared wrappers, and nested declarations.
    root = Node(0)
    outer = Node(1, 10, parent=root)
    wrapper = Node(2, 20, parent=outer)
    inner = Node(3, 30, parent=wrapper)
    body = Node(4, 35, parent=inner)
    leaf = Node(5, 40, parent=body)
    sibling = Node(6, 60, parent=wrapper)
    top = Node(7, 200, 300, parent=root)
    nodes = [top, sibling, leaf, inner, outer]
    items = {node.id: StructureItem(name=str(node.id)) for node in nodes}
    declarations: Any = {(node.id, None): (node, items[node.id]) for node in nodes}

    # When a hierarchy is rebuilt from AST ancestry rather than input order.
    result = structure._structure_hierarchy(declarations)

    # Then each level is source ordered and undeclared wrappers are skipped.
    assert result == [items[outer.id], items[top.id]]
    assert items[outer.id].children == [items[inner.id], items[sibling.id]]
    assert items[inner.id].children == [items[leaf.id]]
    assert items[leaf.id].children == items[sibling.id].children == []
    assert items[top.id].children == []


@pytest.mark.parametrize("existing", [None, [], [StructureItem(name="native")]])
def test_no_query_returns_existing_structure_without_reading_tree(monkeypatch, existing):
    # Given a language without queries and a tree that must not be accessed.
    monkeypatch.setattr(structure, "_declaration_query", lambda language: None)
    syntax = Mock(
        source=SimpleNamespace(language="test"),
        tree=Mock(side_effect=AssertionError("must not parse")),
    )

    # When structure extraction has no query to enrich the native structure.
    result = structure.extract_structure(syntax, existing)

    # Then the supplied list, including an empty list, passes through unchanged.
    if existing is None:
        assert result == []
    else:
        assert result is existing


def test_named_capture_overrides_unnamed_capture_but_not_the_reverse(monkeypatch):
    # Given overlapping captures for one declaration and an unrelated reference.
    install_adapter(monkeypatch)
    node = Node(1)
    name = Node(2, text=b"chosen")
    declarations = {}

    # When an unnamed capture is enriched and then encountered unnamed again.
    structure._add_captured_match({"definition.function": [node]}, "test", declarations)
    structure._add_captured_match(
        {"definition.method": [node], "name": [name]}, "test", declarations
    )
    structure._add_captured_match({"definition.class": [node]}, "test", declarations)
    structure._add_captured_match({"reference.call": [name]}, "test", declarations)

    # Then the explicit name and its definition kind survive later captures.
    assert set(declarations) == {node.id}
    captured_node, item = declarations[node.id]
    assert captured_node is node
    assert (item.name, item.kind) == ("chosen", "method")


def test_extract_structure_merges_captures_and_native_metadata_without_mutation(monkeypatch):
    outer = Node(1, 0, 100)
    wrapper = Node(10, 1, 99, parent=outer)
    inner = Node(2, 10, 30, parent=wrapper)
    excluded = Node(9, 110, 120)
    install_adapter(monkeypatch, normalize_declaration=lambda node:
                    None if node.id == 9 else DeclarationCarrier(outer if node.id == 10 else node))
    root = Node(0, ranges={(1, 98): wrapper, (110, 119): excluded})
    native = [StructureItem(name="outer", span=Span(1, 99), doc_comment="native doc"),
              StructureItem(name="excluded", span=Span(110, 120)),
              StructureItem(name="no matching node", span=Span(130, 140))]
    before = deepcopy(native)
    captures = [(0, {"definition.class": [outer], "name": [Node(3, text=b"outer")]}),
                (0, {"definition.method": [inner], "name": [Node(4, text=b"inner")]}),
                (0, {"definition.class": [excluded]})]
    monkeypatch.setattr(structure, "_declaration_query", lambda language: Mock())
    monkeypatch.setattr(structure, "QueryCursor", lambda query: Mock(matches=lambda tree: captures))
    syntax = Mock(source=SimpleNamespace(language="test"), tree=lambda: root)

    result = structure.extract_structure(syntax, native)

    assert len(result) == 1
    assert result[0].name == "outer"
    assert result[0].doc_comment == "native doc"
    assert result[0].span == Span(0, 100, 2, 3, 4, 5)
    assert [(child.name, child.kind) for child in result[0].children] == [("inner", "method")]
    assert native == before


def test_native_declarations_flatten_children_without_mutating_input():
    # Given a spanless container and a zero-width nested declaration.
    node = Node(1, 5, 5)
    root = Node(0, ranges={(5, 5): node})
    child = StructureItem(name="child", span=Span(5, 5))
    native = StructureItem(name="container", children=[child])
    before = deepcopy(native)

    # When native declarations are mapped back to their AST nodes.
    result = list(structure._native_declarations(root, [native]))

    # Then spanless parents do not hide children or alter the original hierarchy.
    assert result == [(node, child)]
    assert result[0][1] is not child
    assert result[0][1].children == []
    assert native == before
