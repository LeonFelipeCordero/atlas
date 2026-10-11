"""Whole dispatch sources retain one AST carrier and one local call owner."""

from dataclasses import replace
from pathlib import Path

import pytest
from tree_sitter import Node
from tree_sitter_language_pack import ProcessConfig, Span, process

from atlas.domain.models import ParsedRepository
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.adapters import get_adapter
from atlas.parsing.discovery import discover_files
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_parsed, coffee_source, coffee_symbols

LANGUAGES = ("javascript", "typescript", "tsx")
# Dispatch bindings retain their local helpers across native and fallback parsing.
BINDINGS = {
    "prepareOrder": ("hasDrinks", 1, 0),
    "pickupLabel": ("customerLabel", 1, 0),
    "drinkQueue": ("drinkLabel", 1, 2),
    "readyOrders": ("ready", 1, 1),
    "hold": ("holdNote", 2, 0),
    "requeue": ("resetPickup", 1, 0),
    "audit": ("empty", 1, 1),
    "archive": ("archiveEntry", 1, 1),
    "collect": ("queuePosition", 2, 0),
    "receipt": ("itemCount", 1, 0),
    "notifications": ("notification", 1, 1),
    "deliveries": ("delivery", 1, 1),
}
VARIANTS = Path(__file__).parent / "fixtures/variants/parsing/tracking-nontransparent"


def tracking_source(language):
    extension = {"javascript": "js", "typescript": "ts", "tsx": "tsx"}[language]
    return coffee_source(language, f"{'ordering/' if language != 'tsx' else ''}TrackingCarriers.{extension}")


def flatten(items):
    result = []
    stack = list(reversed(items))
    while stack:
        item = stack.pop()
        result.append(item)
        stack.extend(reversed(item.children))
    return result


def span(node: Node):
    return Span(
        start_byte=node.start_byte, end_byte=node.end_byte,
        start_line=node.start_point.row, start_column=node.start_point.column,
        end_line=node.end_point.row, end_column=node.end_point.column,
    )


def binding_context(language, name):
    syntax = ParsedSyntax(tracking_source(language))
    callback = next(item for item in flatten(extract_structure(syntax)) if item.name == name)
    node = syntax.tree().descendant_for_byte_range(callback.span.start_byte, callback.span.end_byte - 1)
    assert node is not None
    assert node.type in get_adapter(language).callback_types
    return syntax, callback, node


def assert_carrier(syntax, node, case):
    name, helper, existing = case
    before = repr(existing)
    matches = [item for item in flatten(extract_structure(syntax, existing)) if item.name == name]
    assert len(matches) == 1
    merged = matches[0]
    assert merged.span == span(node)
    assert [child.name for child in merged.children] == [helper]
    assert syntax.source.source[node.start_byte:node.end_byte] == node.text
    assert repr(existing) == before


def assert_local_owner(file, node, name):
    helper, inputs, helper_inputs = BINDINGS[name]
    owner, = coffee_symbols(file, name)
    local, = coffee_symbols(file, f"{name}.{helper}")
    assert local.parent_key == owner.key
    assert (owner.start_byte, owner.end_byte) == (node.start_byte, node.end_byte)
    call, = [call for call in file.calls if call.name == helper
             and owner.start_byte <= call.start_byte < owner.end_byte]
    assert_local_calls(file, (owner, local, call), name)
    assert owner.key == f"symbol:{file.source.path}::{name}:{node.start_byte}"
    assert owner.kind == local.kind == "function"
    assert owner.parent_key == f"file:{file.source.path}"
    assert (owner.parameter_count, local.parameter_count) == (inputs, helper_inputs)
    assert owner.line_count == node.end_point.row - node.start_point.row + 1


def assert_local_calls(file, symbols, name):
    owner, local, call = symbols
    graph = resolve_connections(ParsedRepository([file]))
    calls = [edge for edge in graph.connections if edge.source_key == owner.key]
    expected = [(local.key, "CALLS", "INFERRED", file.source.path, call.line, call.evidence)]
    if name == "collect":
        mutation, = [call for call in file.calls if call.name == "splice"]
        expected.append((f"external:{file.source.language}:callable:splice", "CALLS", "INFERRED",
                         file.source.path, mutation.line, mutation.evidence))
    assert [(edge.target_key, edge.type, edge.confidence, edge.path, edge.line, edge.evidence)
            for edge in calls] == expected


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("name", BINDINGS)
@pytest.mark.parametrize("use_native", [False, True], ids=["fallback", "native"])
def test_parenthesized_bindings_have_exact_carrier_and_local_owner(language, name, use_native):
    syntax, _, node = binding_context(language, name)
    native = process(syntax.source.source.decode(), ProcessConfig(language=language)).structure if use_native else []
    assert_carrier(syntax, node, (name, BINDINGS[name][0], native))
    assert_local_owner(coffee_parsed(language, syntax.source.path), node, name)


def binding_wrapper(node):
    wrapper = node.parent
    while wrapper is not None and wrapper.type == "parenthesized_expression":
        wrapper = wrapper.parent
    assert wrapper is not None
    return wrapper


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("case", [
    (list(BINDINGS)[:4], "variable_declarator"),
    (list(BINDINGS)[4:8], "assignment_expression"),
    (list(BINDINGS)[8:], "pair"),
])
def test_all_binding_contexts_cover_all_four_carrier_styles(language, case):
    names, context = case
    nodes = [binding_context(language, name)[2] for name in names]
    assert [node.type for node in nodes] == [
        "arrow_function", "function_expression", "generator_function", "generator_function",
    ]
    assert [node.child_by_field_name("name") is not None for node in nodes] == [False, True, True, False]
    assert [binding_wrapper(node).type for node in nodes] == [context] * 4


@pytest.mark.parametrize("language", LANGUAGES)
def test_generator_ancestor_keeps_callback_and_local_call_owner(language):
    file = coffee_parsed(language, tracking_source(language).path)
    outer, = coffee_symbols(file, "trackBatch")
    callback, = coffee_symbols(file, "trackBatch.collectTicket")
    local, = coffee_symbols(file, "trackBatch.collectTicket.batchLabel")
    assert callback.parent_key == outer.key
    assert local.parent_key == callback.key
    assert (outer.parameter_count, callback.parameter_count, local.parameter_count) == (1, 1, 0)
    graph = resolve_connections(ParsedRepository([file]))
    assert [(edge.source_key, edge.target_key, edge.evidence) for edge in graph.connections
            if edge.source_key in {outer.key, callback.key}] == [
                (callback.key, local.key, "batchLabel()"),
                (outer.key, callback.key, "collectTicket(order)"),
            ]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("case", [("dispatchLabel", "internalTicket"), ("queueLabel", "<anonymous>")])
def test_inline_dispatch_callbacks_keep_nearest_owner(language, case):
    file = coffee_parsed(language, tracking_source(language).path)
    dispatch, = coffee_symbols(file, "dispatchOrders")
    symbols = {symbol.key: symbol for symbol in file.symbols}
    graph = resolve_connections(ParsedRepository([file]))
    name, callback_name = case
    helper, = [symbol for symbol in file.symbols if symbol.name == name]
    callback = symbols[helper.parent_key]
    enclosing = symbols[callback.parent_key]
    assert callback.name == callback_name
    assert enclosing.parent_key == dispatch.key
    assert callback.parameter_count == 1
    assert helper.parameter_count == 0
    assert [(edge.source_key, edge.target_key, edge.evidence) for edge in graph.connections
            if edge.target_key == helper.key] == [(callback.key, helper.key, f"{name}()")]


def assert_native_endpoint(binding, wrapper, endpoints):
    syntax, callback, node = binding
    start, end = endpoints
    helper = callback.children[0].name
    native_span = replace(
        span(wrapper), start_byte=start.start_byte, start_line=start.start_point.row,
        start_column=start.start_point.column, end_byte=end.end_byte,
        end_line=end.end_point.row, end_column=end.end_point.column,
    )
    native = replace(
        callback, name="stale pickup name", span=native_span, signature="wrapper signature",
        doc_comment="pickup docs", decorators=["pickup annotation"], visibility="public",
        body_span=callback.children[0].span, children=[],
    )
    originals = [native, replace(native, name=None), replace(native, name="")]
    before = repr(originals)
    items = flatten(extract_structure(syntax, originals))
    matches = [item for item in items if item.span == span(node)]
    assert len(matches) == 1
    assert not any(item.name == "stale pickup name" for item in items)
    assert sum(item.doc_comment == "pickup docs" for item in items) == 1
    merged = matches[0]
    assert merged.name == callback.name
    assert merged.signature == node.text.decode()
    assert merged.doc_comment == "pickup docs"
    assert merged.decorators == ["pickup annotation"]
    assert merged.visibility == "public"
    assert merged.body_span == callback.children[0].span
    assert [child.name for child in merged.children] == [helper]
    assert repr(originals) == before


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("name", (*BINDINGS, "internalTicket"))
@pytest.mark.parametrize("endpoint", ["both", "start", "end"])
def test_native_wrappers_correct_both_endpoints_without_mutation(language, name, endpoint):
    binding = binding_context(language, name)
    syntax, _, node = binding
    assert syntax.source.source[:node.start_byte].decode().find("café") >= 0
    wrapper = node.parent
    count = 0
    while wrapper is not None and wrapper.type in {
        "parenthesized_expression", "variable_declarator", "assignment_expression", "pair",
    }:
        start = node if endpoint == "end" else wrapper
        end = node if endpoint == "start" else wrapper
        assert_native_endpoint(binding, wrapper, (start, end))
        count += 1
        wrapper = wrapper.parent
    assert count >= 2


@pytest.mark.parametrize("language", LANGUAGES)
def test_unresolved_binding_preserves_native_name_and_metadata_once(language):
    syntax = ParsedSyntax(tracking_source(language))
    callback = next(item for item in flatten(extract_structure(syntax))
                    if item.name is None and [child.name for child in item.children] == ["queueLabel"])
    native = replace(callback, name="queued ticket", doc_comment="queue docs", children=[])
    originals = [native, replace(native, name=None), replace(native, name="")]
    before = repr(originals)
    matches = [item for item in flatten(extract_structure(syntax, originals)) if item.span == callback.span]
    assert len(matches) == 1
    assert matches[0].name == "queued ticket"
    assert matches[0].doc_comment == "queue docs"
    assert [child.name for child in matches[0].children] == ["queueLabel"]
    assert repr(originals) == before


def receipt_callbacks(syntax, use_native):
    native = process(syntax.source.source.decode(),
                     ProcessConfig(language=syntax.source.language)).structure if use_native else []
    owner, = extract_structure(syntax, native)
    assert owner.name == "receiptPickup"
    return owner.children


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("use_native", [False, True], ids=["fallback", "native"])
def test_only_parentheses_are_transparent_and_inline_names_stay_explicit(language, use_native):
    source, = [source for source in discover_files(VARIANTS) if source.language == language]
    syntax = ParsedSyntax(source)
    assert not syntax.tree().has_error
    items = receipt_callbacks(syntax, use_native)
    assert [item.name for item in items] == [
        "trackingLabel", None, None, None, None, "explicitTicket", "ticketGenerator", None,
    ]
    assert len(flatten(items)) == 8
    nodes: list[Node] = [node for node in walk(syntax.tree()) if node.type in get_adapter(language).callback_types]
    assert len(nodes) == 8
    actual = set()
    for item in items:
        assert item.span is not None
        actual.add((item.span.start_byte, item.span.end_byte))
    assert actual == {(node.start_byte, node.end_byte) for node in nodes}
