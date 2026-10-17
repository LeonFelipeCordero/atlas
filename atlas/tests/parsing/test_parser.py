"""Parser contracts with native processing and grammar boundaries replaced."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from tree_sitter_language_pack import Span, StructureItem

from atlas.domain.models import Call, ParsedFile, SourceFile
from atlas.parsing import parser


def source(data=b"run()", path="main.py", language="python"):
    return SourceFile(path, Path("/repo") / path, language, data)


def node(**overrides) -> Any:
    values = dict(has_error=False, is_error=False, is_missing=False, children=[], start_point=(0, 0))
    return SimpleNamespace(**(values | overrides))


@pytest.fixture
def boundary(monkeypatch):
    root = node()
    adapter = SimpleNamespace(
        imports=lambda syntax, native: native,
        inheritance=lambda header: [],
    )
    native = SimpleNamespace(imports=[], structure=[])
    monkeypatch.setattr(parser, "get_adapter", lambda language: adapter)
    monkeypatch.setattr(parser, "_parse_syntax", Mock(return_value=root))
    monkeypatch.setattr(parser, "_extract_calls", Mock(return_value=[]))
    monkeypatch.setattr(parser, "process", Mock(return_value=native))
    monkeypatch.setattr(parser, "extract_structure", Mock(return_value=[]))
    return SimpleNamespace(root=root, adapter=adapter, native=native)


def test_parse_file_preserves_original_bytes_and_hash_but_normalizes_parser_input(monkeypatch, boundary):
    original = source(b"\xff\r\nrun()")
    observed = {}
    calls = [Call("main.py", "run", 5, 10, 2, "run()", True)]

    def extract_calls(file, *, root, adapter):
        observed["calls"] = (file, root, adapter)
        return calls

    def syntax(file, adapter):
        observed["syntax"] = file
        return boundary.root

    def process(text, config):
        observed["text"] = text
        observed["language"] = config.language
        return boundary.native

    def imports(syntax, native):
        observed["imports"] = syntax
        return [("adapter.import", 7)]

    def structure(syntax, native):
        observed["structure"] = syntax
        return []

    monkeypatch.setattr(parser, "_parse_syntax", syntax)
    monkeypatch.setattr(parser, "_extract_calls", extract_calls)
    monkeypatch.setattr(parser, "process", process)
    monkeypatch.setattr(parser, "extract_structure", structure)
    boundary.adapter.imports = imports

    result = parser.parse_file(original)

    assert result.source is original
    assert result.content_hash == hashlib.sha256(original.source).hexdigest()
    assert result.parse_error is None
    assert observed["syntax"] == source(b"\xef\xbf\xbd\r\nrun()")
    assert observed["text"] == "\ufffd\r\nrun()"
    assert observed["language"] == "python"
    assert observed["imports"] is observed["structure"]
    assert observed["imports"].source == observed["syntax"]
    assert observed["imports"].root is boundary.root
    call_source, call_root, call_adapter = observed["calls"]
    assert call_source is observed["syntax"]
    assert call_root is boundary.root
    assert call_adapter is boundary.adapter
    assert result.calls == calls
    assert [(item.file_path, item.source, item.line) for item in result.imports] == [
        ("main.py", "adapter.import", 7)
    ]


def test_native_imports_skip_missing_spans_and_convert_line_numbers(boundary):
    boundary.native.imports = [
        SimpleNamespace(source="ignored", span=None),
        SimpleNamespace(source="first", span=Span(0, 1, 0)),
        SimpleNamespace(source="later", span=Span(2, 3, 4)),
    ]

    result = parser.parse_file(source())

    assert [(item.source, item.line) for item in result.imports] == [("first", 1), ("later", 5)]


@pytest.mark.parametrize("generic", [False, True])
def test_only_dedicated_adapters_report_syntax_diagnostics(monkeypatch, boundary, generic):
    boundary.root.has_error = True
    boundary.root.children = [node(is_missing=True, start_point=(2, 4))]
    if generic:
        monkeypatch.setattr(parser, "DEFAULT_ADAPTER", boundary.adapter)

    result = parser.parse_file(source())

    assert result.parse_error == (None if generic else
        "Syntax error at line 3, column 5; analysis may be incomplete.")


@pytest.mark.parametrize("root", [None, node(), node(has_error=True)])
def test_syntax_flags_without_concrete_error_do_not_invent_diagnostics(root):
    assert parser._syntax_error(root) is None


def test_syntax_diagnostic_uses_first_concrete_error_in_source_order():
    root = node(has_error=True, children=[
        node(children=[node(is_error=True, start_point=(1, 8))]),
        node(is_missing=True, start_point=(3, 0)),
    ])

    assert parser._syntax_error(root) == "Syntax error at line 2, column 9; analysis may be incomplete."


@pytest.mark.parametrize("stage", ["_parse_syntax", "_extract_calls", "process", "extract_structure"])
def test_parser_boundary_failures_propagate_without_partial_records(monkeypatch, boundary, stage):
    failure = RuntimeError(stage)
    monkeypatch.setattr(parser, stage, Mock(side_effect=failure))

    with pytest.raises(RuntimeError) as caught:
        parser.parse_file(source())

    assert caught.value is failure


def test_nested_symbols_have_stable_identity_coordinates_and_inheritance(monkeypatch, boundary):
    child = StructureItem(name=None, kind="method", span=Span(10, 20, 2, 3, 4, 5))
    parent = StructureItem(
        name="Brew", kind="class", span=Span(0, 30, 0, 1, 5, 6),
        signature="class Brew(Base)", visibility="public", decorators=["@coffee"],
        children=[child],
    )
    monkeypatch.setattr(parser, "extract_structure", lambda *args: [
        StructureItem(name="spanless", children=[child]), parent,
    ])
    boundary.adapter.inheritance = lambda header: ["Base"] if (
        header.kind == "class" and header.signature == "class Brew(Base)"
    ) else []

    result = parser.parse_file(source())

    assert len(result.symbols) == 2
    outer, inner = result.symbols
    assert (outer.key, outer.qualified_name, outer.parent_key) == (
        "symbol:main.py::Brew:0", "main.py::Brew", "file:main.py",
    )
    assert (outer.start_line, outer.start_column, outer.end_line, outer.end_column) == (1, 2, 6, 7)
    assert (outer.name, outer.kind, outer.signature, outer.visibility, outer.decorators) == (
        "Brew", "class", "class Brew(Base)", "public", ["@coffee"],
    )
    assert (inner.key, inner.qualified_name, inner.parent_key) == (
        "symbol:main.py::Brew.<anonymous>:10", "main.py::Brew.<anonymous>", outer.key,
    )
    assert (inner.start_byte, inner.end_byte, inner.start_line, inner.start_column,
            inner.end_line, inner.end_column) == (10, 20, 3, 4, 5, 6)
    assert len(result.inheritances) == 1
    inheritance = result.inheritances[0]
    assert (inheritance.source_key, inheritance.target_name, inheritance.line, inheritance.evidence) == (
        outer.key, "Base", 1, "class Brew(Base)",
    )


def test_extract_calls_preserves_offset_line_relationship_and_excerpt(monkeypatch):
    file = source(b"prefix\n" + b"x" * 301 + b"\xff")
    site = (node(start_byte=0, end_byte=302), 7, False, ())
    skipped = (node(start_byte=0, end_byte=1), 0, False, ())
    adapter = Mock(
        call_sites=lambda root: [skipped, site],
        normalize_call=lambda candidate: (None, False, None) if candidate is skipped else ("brew", False, "service"),
        call_relationship=lambda candidate: "REFERENCES",
    )

    calls = parser._extract_calls(file, root=node(), adapter=adapter)

    assert len(calls) == 1
    call = calls[0]
    assert (call.file_path, call.name, call.start_byte, call.end_byte, call.line) == (
        "main.py", "brew", 7, 309, 2,
    )
    assert (call.evidence, call.bare_target, call.qualifier, call.relationship) == (
        "x" * 300, False, "service", "REFERENCES",
    )


@pytest.mark.parametrize("needs_tree", ["none", "calls", "custom", "imports", "declarations"])
def test_parse_syntax_only_builds_a_tree_when_needed(monkeypatch, needs_tree):
    adapter = Mock(
        call_sites=(lambda root: []) if needs_tree == "custom" else parser.call_sites,
        import_node=object() if needs_tree == "imports" else None,
    )
    root = node()
    native_parser = Mock()
    native_parser.parse.return_value.root_node = root
    if needs_tree == "none":
        native_parser.parse.side_effect = AssertionError("unnecessary parse")
    monkeypatch.setattr(parser, "get_parser", lambda language: native_parser)
    monkeypatch.setattr(parser, "_has_call_nodes", lambda language: needs_tree == "calls")
    monkeypatch.setattr(parser, "_declaration_query", lambda language: object() if needs_tree == "declarations" else None)

    result = parser._parse_syntax(source(), adapter)

    assert result is (None if needs_tree == "none" else root)


def test_data_grammar_skips_fallback_call_parser(monkeypatch):
    monkeypatch.setattr(parser, "_has_call_nodes", lambda language: False)
    monkeypatch.setattr(parser, "get_parser", Mock(side_effect=AssertionError("must not parse")))
    adapter = Mock(call_sites=parser.call_sites)

    assert parser._extract_calls(source(language="json"), adapter=adapter) == []


def test_standalone_calls_use_selected_adapter_and_parse_source(monkeypatch):
    file = source(b"\xff()")
    root = node()
    native_parser = Mock()
    native_parser.parse.return_value.root_node = root
    adapter = Mock(
        call_sites=lambda tree: [(node(start_byte=0, end_byte=3), 0, False, ())] if tree is root else [],
        normalize_call=lambda site: ("brew", True, None),
        call_relationship=lambda site: "CALLS",
    )
    monkeypatch.setattr(parser, "get_parser", lambda language: native_parser)
    monkeypatch.setattr(parser, "get_adapter", lambda language: adapter)

    calls = parser._extract_calls(file)

    assert [(call.name, call.evidence, call.bare_target, call.qualifier) for call in calls] == [
        ("brew", "\ufffd()", True, None),
    ]


@pytest.mark.parametrize("fallback", [True, False])
def test_call_capability_guard_preserves_fallback_and_custom_calls(monkeypatch, fallback):
    # Fallback calls need grammar support; custom adapters can use other carriers.
    site = (node(start_byte=0, end_byte=5), 0, False, ())

    def fallback_sites(root):
        return [site]

    monkeypatch.setattr(parser, "call_sites", fallback_sites)
    monkeypatch.setattr(parser, "_has_call_nodes", lambda language: fallback)
    adapter = Mock(
        call_sites=fallback_sites if fallback else lambda root: [site],
        normalize_call=lambda candidate: ("run", True, None),
        call_relationship=lambda candidate: "CALLS",
    )

    calls = parser._extract_calls(source(), root=node(), adapter=adapter)

    assert [(call.name, call.evidence, call.relationship) for call in calls] == [
        ("run", "run()", "CALLS"),
    ]


def test_parse_files_preserves_order_and_duplicates(monkeypatch):
    first, second = source(path="b.py"), source(path="a.py")
    monkeypatch.setattr(parser, "parse_file", lambda file: ParsedFile(file, "hash", None))

    result = parser.parse_files([first, second, first])

    assert [file.source for file in result.files] == [first, second, first]
    assert parser.parse_files([]).files == []


def test_parse_files_does_not_hide_a_failed_source(monkeypatch):
    failure = ValueError("bad grammar")
    monkeypatch.setattr(parser, "parse_file", Mock(side_effect=[ParsedFile(source(), "hash", None), failure]))

    with pytest.raises(ValueError) as caught:
        parser.parse_files([source(), source(path="bad.py")])

    assert caught.value is failure
