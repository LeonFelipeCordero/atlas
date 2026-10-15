"""Source-grounded parser records and native metadata on complete coffee files."""

from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest
from tree_sitter_language_pack import ProcessConfig, Span, StructureItem, process

from atlas.domain.models import SourceFile, file_key
from atlas.parsing.parser import parse_file, parse_files
from atlas.parsing.structure import _declaration_query, extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import LANGUAGES, coffee_sources
from tests.variant_snapshot_support import scenario_sources, VARIANT_ROOT
from tests.project_snapshot_support import structure_value


PARSING_VARIANTS = Path(__file__).parent / "fixtures/variants/parsing"


PRIMARY_SYMBOLS = {
    "java": ("orders/Order.java", "Order"),
    "kotlin": ("orders/Order.kt", "Order"),
    "go": ("brewing/order.go", "NewOrder"),
    "rust": ("brewing/recipe.rs", "Recipe"),
    "javascript": ("ordering/OrderService.js", "OrderService.fulfill"),
    "typescript": ("ordering/OrderService.ts", "OrderService.fulfill"),
    "elixir": ("brewing/order.ex", "Coffee.Brewing.Order.new"),
    "python": ("src/coffee/orders/models.py", "Order.transition"),
    "tsx": ("App.tsx", "Menu"),
}


def items_tree(items):
    for item in items:
        yield item
        yield from items_tree(item.children)


def assert_symbol_record(file, symbol, symbols):
    source = file.source
    assert symbol.file_path == source.path
    assert symbol.language == source.language
    assert symbol.key == f"symbol:{symbol.qualified_name}:{symbol.start_byte}"
    assert 0 <= symbol.start_byte < symbol.end_byte <= len(source.source)
    assert symbol.start_line == source.source[:symbol.start_byte].count(b"\n") + 1
    assert symbol.complexity is symbol.parameter_count is symbol.line_count is None
    if symbol.parent_key != file_key(source.path):
        parent = symbols[symbol.parent_key]
        assert parent.start_byte <= symbol.start_byte < symbol.end_byte <= parent.end_byte
        assert symbol.qualified_name.startswith(parent.qualified_name + ".")


def assert_call_record(source, call):
    assert call.file_path == source.path
    assert source.source[call.start_byte:call.end_byte].decode()[:300] == call.evidence
    assert call.line == source.source[:call.start_byte].count(b"\n") + 1


def assert_import_record(source, item):
    text = source.source.decode()
    assert item.file_path == source.path
    assert item.source.strip() in text
    assert item.source.strip().splitlines()[0] in text.splitlines()[item.line - 1]


def assert_file_record(file):
    assert file.parse_error is None, file.source.path
    assert file.content_hash == sha256(file.source.source).hexdigest()
    assert asdict(parse_file(file.source)) == asdict(file)
    symbols = {symbol.key: symbol for symbol in file.symbols}
    for symbol in file.symbols:
        assert_symbol_record(file, symbol, symbols)
    for call in file.calls:
        assert_call_record(file.source, call)
    for item in file.imports:
        assert_import_record(file.source, item)


def assert_repository_records(repo, language):
    assert len({symbol.key for symbol in repo.symbols}) == len(repo.symbols)
    path, name = PRIMARY_SYMBOLS[language]
    assert any(symbol.qualified_name == f"{path}::{name}" for symbol in repo.symbols)
    assert repo.calls
    assert repo.imports


@pytest.mark.parametrize("language", LANGUAGES)
def test_parser_records(language):
    sources = coffee_sources(language)
    before = [asdict(source) for source in sources]
    repo = parse_files(sources)
    assert [file.source.path for file in repo.files] == [source.path for source in sources]
    assert [asdict(source) for source in sources] == before
    assert_repository_records(repo, language)
    for file in repo.files:
        assert_file_record(file)


def assert_hierarchy(items, size, parent=None):
    starts = []
    for item in items:
        assert item.span is not None
        span = item.span
        assert 0 <= span.start_byte < span.end_byte <= size
        starts.append(span.start_byte)
        if parent:
            assert parent.start_byte <= span.start_byte < span.end_byte <= parent.end_byte
        assert_hierarchy(item.children, size, span)
    assert starts == sorted(starts)


def structure_spans(items):
    return {(item.name, item.span.start_byte, item.span.end_byte)
            for item in items_tree(items) if item.span}


def assert_native_structure(source):
    native = process(source.source.decode(), ProcessConfig(language=source.language)).structure
    before = structure_value(native)
    syntax = ParsedSyntax(source)
    tagged = extract_structure(syntax, [])
    merged = extract_structure(syntax, native)
    assert structure_value(native) == before, source.path
    assert structure_value(extract_structure(syntax, native)) == structure_value(merged)
    assert_hierarchy(tagged, len(source.source))
    assert_hierarchy(merged, len(source.source))
    native_ids = {id(item) for item in items_tree(native)}
    assert all(id(item) not in native_ids for item in items_tree(merged))
    assert structure_spans(tagged) <= structure_spans(merged), source.path


@pytest.mark.parametrize("language", LANGUAGES)
def test_structure_native_variants(language):
    for source in coffee_sources(language):
        assert_native_structure(source)


def node_span(node):
    return Span(start_byte=node.start_byte, end_byte=node.end_byte,
                start_line=node.start_point.row, start_column=node.start_point.column,
                end_line=node.end_point.row, end_column=node.end_point.column)


def scheduling_syntax(language, grammar):
    source = next(source for source in coffee_sources(language)
                  if source.path.endswith("/Scheduling.js") or source.path.endswith("/Scheduling.ts"))
    return ParsedSyntax(replace(source, language=grammar))


@pytest.mark.parametrize("language,grammar", [
    ("javascript", "javascript"),
    ("typescript", "typescript"), ("typescript", "tsx"),
])
@pytest.mark.parametrize("name", [
    "scheduleDrink", "scheduleBatch", "pickupLabel", "scheduledTickets", "namedTickets", "total",
])
def test_native_wrappers_canonicalize_both_endpoints_without_mutation(language, grammar, name):
    syntax = scheduling_syntax(language, grammar)
    parsed = parse_file(syntax.source)
    symbol, = [symbol for symbol in parsed.symbols if symbol.name == name]
    canonical = syntax.tree().descendant_for_byte_range(symbol.start_byte, symbol.end_byte - 1)
    assert canonical is not None
    assert canonical.type in {"arrow_function", "function_expression", "generator_function"}
    wrapper = canonical
    while wrapper is not None and wrapper.type in {
        "arrow_function", "function_expression", "generator_function",
        "parenthesized_expression", "variable_declarator",
    }:
        assert_native_wrapper(syntax, symbol, (wrapper, canonical))
        wrapper = wrapper.parent


def assert_native_wrapper(syntax, symbol, endpoints):
    wrapper, canonical = endpoints
    native = StructureItem(name="stale-binding", kind="method", span=node_span(wrapper),
                           signature="native scheduling metadata", visibility="private",
                           decorators=["scheduled"], doc_comment="pickup policy",
                           body_span=node_span(canonical))
    duplicates = [native, replace(native, name="duplicate-native-name")]
    before = structure_value(duplicates)
    merged = extract_structure(syntax, duplicates)
    assert structure_value(duplicates) == before
    result, = [item for item in items_tree(merged) if item.name == symbol.name]
    assert result.span is not None
    assert (result.span.start_byte, result.span.end_byte) == (symbol.start_byte, symbol.end_byte)
    assert str(result.kind).lower() == "function"
    assert result.visibility == "private" and result.decorators == ["scheduled"]
    assert result.doc_comment == "pickup policy"
    assert result.body_span == native.body_span
    expected_signature = "native scheduling metadata" if wrapper == canonical else canonical.text.decode()
    assert result.signature == expected_signature


@pytest.mark.parametrize("variant", [
    "missing-parameter-delimiter", "missing-condition-colon", "invalid-utf8-string",
])
def test_malformed_and_invalid_utf8_records_preserve_original_bytes(variant):
    path = PARSING_VARIANTS / variant / "scheduling.py"
    source_bytes = path.read_bytes()
    source = SourceFile(path.name, path, "python", source_bytes)
    before = asdict(source)
    parsed = parse_file(source)
    assert parsed.source.source == source_bytes
    assert asdict(source) == before
    assert parsed.content_hash == sha256(source_bytes).hexdigest()
    if b"\xff" in source_bytes:
        assert parsed.parse_error is None
        symbol, = parsed.symbols
        normalized = source_bytes.decode(errors="replace").encode()
        assert b"\xef\xbf\xbd" in normalized
        assert symbol.end_byte == len(normalized) - 1
        repaired = parse_file(replace(source, source=normalized))
        assert parsed.symbols == repaired.symbols
        assert parsed.calls == repaired.calls
        assert parsed.content_hash != repaired.content_hash
    else:
        assert parsed.parse_error and parsed.parse_error.startswith("Syntax error at line ")


def test_missing_tags_preserve_native_list_and_metadata():
    source, = scenario_sources(VARIANT_ROOT / "lua/generic-fallback")
    syntax = ParsedSyntax(source)
    native = process(source.source.decode(), ProcessConfig(language="lua")).structure
    assert any(item.name == "dispatch" for item in items_tree(native))
    before = structure_value(native)
    _declaration_query.cache_clear()
    try:
        with patch("atlas.parsing.structure.get_tags_query", return_value=None):
            assert extract_structure(syntax, native) is native
            assert extract_structure(syntax) == []
        assert structure_value(native) == before
    finally:
        _declaration_query.cache_clear()
