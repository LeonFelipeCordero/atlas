"""Parenthesized callback bindings have one carrier in parsing and resolution."""

from tests.source_snapshot_fixture import case_bytes, case_text

import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from tests.parsing_snapshot_support import assert_parser_snapshot, source_variants

from tree_sitter import Node
from tree_sitter_language_pack import (
    ProcessConfig,
    Span,
    StructureItem,
    get_parser,
    process,
)

from atlas.parsing.adapters import get_adapter
from atlas.parsing.discovery import SourceFile
from atlas.domain.models import ParsedRepository
from atlas.parsing.parser import parse_file
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.parsing_fixture import parsing_syntax


LANGUAGES = ("javascript", "typescript", "tsx")
CALLBACKS = (
    case_text('parsing', 'callback-fragment-arrow', 'sample.js'),
    case_text('parsing', 'callback-fragment-named-function', 'sample.js'),
    case_text('parsing', 'callback-fragment-named-generator', 'sample.js'),
    case_text('parsing', 'callback-fragment-anonymous-generator', 'sample.js'),
)

def walk(root: Node) -> list[Node]:
    nodes = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.named_children))
    return nodes


def flatten(items: list[StructureItem]) -> list[StructureItem]:
    result = []
    stack = list(reversed(items))
    while stack:
        item = stack.pop()
        result.append(item)
        stack.extend(reversed(item.children))
    return result


def span(node: Node) -> Span:
    return Span(
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        start_line=node.start_point.row,
        start_column=node.start_point.column,
        end_line=node.end_point.row,
        end_column=node.end_point.column,
    )


@dataclass(frozen=True)
class BindingCase:
    syntax: ParsedSyntax
    name: str
    callback_text: str


@dataclass(frozen=True)
class WrapperContext:
    syntax: ParsedSyntax
    name: str
    callback_node: Node
    callback: StructureItem
    local: StructureItem


class CallbackCarrierRegressionTests(unittest.TestCase):
    def test_exact_parser_and_resolved_graph_for_reported_arrow(self) -> None:
        source = case_bytes('parsing', 'callback_carrier_regression-exact_parser_and_resolved_graph_for_reported_arrow-javascript', 'main.js')
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_reported_arrow(source, language)

    def assert_reported_arrow(self, source: bytes, language: str) -> None:
        parsed = parse_file(SourceFile("main.js", Path("main.js"), language, source))
        self.assertIsNone(parsed.parse_error)
        self.assertEqual(len(parsed.symbols), 2)
        callback, local = parsed.symbols
        assert_parser_snapshot(parsed, 'test_callback_carrier_regression',
                               'test_exact_parser_and_resolved_graph_for_reported_arrow')
        self.assert_reported_calls_and_graph(parsed, callback, local)

    def assert_reported_calls_and_graph(self, parsed, callback, local) -> None:
        graph = resolve_connections(ParsedRepository([parsed]))
        self.assertEqual(
            [
                (
                    e.source_key,
                    e.target_key,
                    e.type,
                    e.confidence,
                    e.path,
                    e.line,
                    e.evidence,
                )
                for e in graph.connections
            ],
            [
                (
                    callback.key,
                    local.key,
                    "CALLS",
                    "INFERRED",
                    "main.js",
                    1,
                    "local()",
                )
            ],
        )
        self.assertEqual(graph.external_nodes, [])

    def assert_binding_context(self, language, source, name, callback_text) -> None:
        native = process(source, ProcessConfig(language=language)).structure
        case = BindingCase(ParsedSyntax(SourceFile("main.js", Path("main.js"), language, source.encode())), name, callback_text)
        self.assert_binding_structure(case, native)
        self.assert_binding_graph(source, language, name)

    def assert_binding_structure(self, case: BindingCase, native):
        for existing in ([], native):
            self.assert_binding_item(case, existing)

    def assert_binding_item(self, case: BindingCase, existing):
        items = extract_structure(case.syntax, existing)
        self.assertEqual([item.name for item in items], [case.name])
        callback = items[0]
        self.assertEqual([child.name for child in callback.children], ["local"])
        start = case.syntax.source.source.index(case.callback_text.encode())
        self.assertIsNotNone(callback.span)
        assert callback.span is not None
        self.assertEqual(
            (callback.span.start_byte, callback.span.end_byte),
            (start, start + len(case.callback_text)),
        )

    def assert_binding_graph(self, source, language, name):
        parsed = parse_file(
            SourceFile("main.js", Path("main.js"), language, source.encode())
        )
        self.assertIsNone(parsed.parse_error)
        self.assertEqual([s.name for s in parsed.symbols], [name, "local"])
        callback_symbol, local = parsed.symbols
        self.assertEqual(local.parent_key, callback_symbol.key)
        graph = resolve_connections(ParsedRepository([parsed]))
        self.assertEqual(
            [(e.source_key, e.target_key, e.evidence) for e in graph.connections],
            [(callback_symbol.key, local.key, "local()")],
        )
        self.assertEqual(graph.external_nodes, [])

    def test_parenthesized_arrow_named_expression_and_generators_in_bindings(
        self,
    ) -> None:
        for language in LANGUAGES:
            cases = source_variants('test_callback_carrier_regression', 'test_parenthesized_arrow_named_expression_and_generators_in_bindings', language)
            for index, case in enumerate(cases):
                with self.subTest(case=case['case_id']):
                    source = case_text(case['family'], case['case_id'], case['path'])
                    self.assert_binding_context(language, source, ('f', 'action', 'apply')[index // 4], CALLBACKS[index % 4])

    def test_generator_ancestor_keeps_callback_and_local_call_owner(self) -> None:
        source = case_text('parsing', 'callback_carrier_regression-generator_ancestor_keeps_callback_and_local_call_owner-javascript', 'main.js')
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_generator_ancestor(source, language)

    def assert_generator_ancestor(self, source, language):
        parsed = parse_file(
            SourceFile("main.js", Path("main.js"), language, source.encode())
        )
        self.assertEqual([s.name for s in parsed.symbols], ["outer", "f", "local"])
        outer, callback, local = parsed.symbols
        self.assertEqual(callback.parent_key, outer.key)
        self.assertEqual(local.parent_key, callback.key)
        graph = resolve_connections(ParsedRepository([parsed]))
        self.assertEqual(
            [(e.source_key, e.target_key, e.evidence) for e in graph.connections],
            [
                (callback.key, local.key, "local()"),
                (outer.key, callback.key, "f()"),
            ],
        )
        self.assertEqual(graph.external_nodes, [])

    def assert_native_wrappers(self, source: str, language: str, name: str) -> None:
        root = get_parser(language).parse(source.encode()).root_node
        nodes = walk(root)
        callback_node = next(
            node for node in nodes if node.type in get_adapter(language).callback_types
        )
        tagged = extract_structure(parsing_syntax(source, language))
        callback = tagged[0]
        local = callback.children[0]
        wrappers = []
        parent = callback_node.parent
        while parent is not None and parent.type in {
            "parenthesized_expression",
            "variable_declarator",
            "assignment_expression",
            "pair",
        }:
            wrappers.append(parent)
            parent = parent.parent
        context = WrapperContext(ParsedSyntax(SourceFile("main.js", Path("main.js"), language, source.encode())), name, callback_node, callback, local)
        for wrapper in wrappers:
            self.assert_wrapper_endpoints(context, wrapper)

    def assert_wrapper_endpoints(self, context: WrapperContext, wrapper):
        callback_node = context.callback_node
        for start, end in (
            (wrapper, wrapper),
            (wrapper, callback_node),
            (callback_node, wrapper),
        ):
            self.assert_native_endpoint(context, (wrapper, start, end))

    def assert_native_endpoint(self, context: WrapperContext, endpoints):
        callback_node, callback, local = context.callback_node, context.callback, context.local
        wrapper, start, end = endpoints
        native_span = replace(
            span(wrapper),
            start_byte=start.start_byte,
            start_line=start.start_point.row,
            start_column=start.start_point.column,
            end_byte=end.end_byte,
            end_line=end.end_point.row,
            end_column=end.end_point.column,
        )
        native = replace(
            callback,
            name="stale native name",
            span=native_span,
            signature="wrapper signature",
            doc_comment="native docs",
            decorators=["native annotation"],
            visibility="public",
            body_span=local.span,
            children=[],
        )
        original = repr(native)
        items = extract_structure(context.syntax, [native])
        self.assertEqual(len(items), 1)
        merged = items[0]
        self.assertEqual(merged.name, context.name)
        self.assertEqual(merged.span, span(callback_node))
        self.assertEqual(
            merged.signature,
            callback_node.text.decode() if callback_node.text else "",
        )
        self.assertEqual(merged.doc_comment, "native docs")
        self.assertEqual(merged.decorators, ["native annotation"])
        self.assertEqual(merged.visibility, "public")
        self.assertEqual(merged.body_span, local.span)
        self.assertEqual([child.name for child in merged.children], ["local"])
        self.assertEqual(repr(native), original)

    def test_native_binding_and_parenthesis_spans_correct_both_endpoints(self) -> None:
        for language in LANGUAGES:
            cases = source_variants('test_callback_carrier_regression', 'test_native_binding_and_parenthesis_spans_correct_both_endpoints', language)
            for name, case in zip(('f', 'action', 'apply', 'internal'), cases, strict=True):
                with self.subTest(case=case['case_id']):
                    source = case_text(case['family'], case['case_id'], case['path'])
                    self.assert_native_wrappers(source, language, name)

    def test_unresolved_binding_preserves_native_name_and_metadata_once(self) -> None:
        source = case_text('parsing', 'callback_carrier_regression-unresolved_binding_preserves_native_name_and_metadata_once-javascript', 'sample.js')
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_unresolved_binding(source, language)

    def assert_unresolved_binding(self, source, language):
        tagged = extract_structure(parsing_syntax(source, language))[0]
        native = replace(
            tagged,
            name="native callback",
            doc_comment="native docs",
            children=[],
        )
        items = extract_structure(
            parsing_syntax(source, language),
            [
                native,
                replace(native, name=None),
                replace(native, name=""),
            ],
        )
        self.assertEqual([i.name for i in items], ["native callback"])
        self.assertEqual(items[0].doc_comment, "native docs")
        self.assertEqual([i.name for i in items[0].children], ["local"])

    def test_only_parentheses_are_transparent_and_inline_names_stay_explicit(
        self,
    ) -> None:
        source = case_text('parsing', 'callback_carrier_regression-only_parentheses_are_transparent_and_inline_names_stay_explicit-javascript', 'sample.js')
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_transparent_parentheses(source, language)

    def assert_transparent_parentheses(self, source, language):
        items = extract_structure(parsing_syntax(source, language))
        self.assertEqual(
            [item.name for item in items],
            ["f", None, None, None, None, "explicit", "generator", None],
        )
        self.assertEqual(len(flatten(items)), 8)


if __name__ == "__main__":
    unittest.main()
