"""Parenthesized callback bindings have one carrier in parsing and resolution."""

import unittest
from dataclasses import replace
from pathlib import Path
from itertools import product

from tree_sitter import Node
from tree_sitter_language_pack import (
    ProcessConfig,
    Span,
    StructureItem,
    get_parser,
    process,
)

from atlas.adapters import get_adapter
from atlas.discovery import SourceFile
from atlas.domain.models import ParsedRepository
from atlas.extraction.parser import parse_file
from atlas.domain.resolver import resolve_connections
from atlas.extraction.structure import extract_structure


LANGUAGES = ("javascript", "typescript", "tsx")
CALLBACKS = (
    "() => { function local() {} return local(); }",
    "function internal() { function local() {} return local(); }",
    "function* internal() { function local() {} yield local(); }",
    "function* () { function local() {} yield local(); }",
)
CONTEXTS = (
    ("const f = (((%s)));", "f"),
    ("object.action = (((%s)));", "action"),
    ("const holder = { apply: (((%s))) };", "apply"),
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


class CallbackCarrierRegressionTests(unittest.TestCase):
    def test_exact_parser_and_resolved_graph_for_reported_arrow(self) -> None:
        source = b"const f = (() => { function local() {} return local(); });"
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_reported_arrow(source, language)

    def assert_reported_arrow(self, source: bytes, language: str) -> None:
        parsed = parse_file(SourceFile("main.js", Path("main.js"), language, source))
        self.assertIsNone(parsed.parse_error)
        self.assertEqual(len(parsed.symbols), 2)
        callback, local = parsed.symbols
        self.assertEqual(
            [
                (
                    s.key,
                    s.name,
                    s.qualified_name,
                    s.kind,
                    s.parent_key,
                    s.start_byte,
                    s.end_byte,
                    s.start_line,
                    s.start_column,
                    s.end_line,
                    s.end_column,
                )
                for s in parsed.symbols
            ],
            [
                (
                    "symbol:main.js::f:11",
                    "f",
                    "main.js::f",
                    "function",
                    "file:main.js",
                    11,
                    56,
                    1,
                    12,
                    1,
                    57,
                ),
                (
                    "symbol:main.js::f.local:19",
                    "local",
                    "main.js::f.local",
                    "function",
                    callback.key,
                    19,
                    38,
                    1,
                    20,
                    1,
                    39,
                ),
            ],
        )
        self.assert_reported_calls_and_graph(parsed, callback, local)

    def assert_reported_calls_and_graph(self, parsed, callback, local) -> None:
        self.assertEqual(
            [
                (
                    c.name,
                    c.start_byte,
                    c.end_byte,
                    c.line,
                    c.evidence,
                    c.bare_target,
                    c.qualifier,
                )
                for c in parsed.calls
            ],
            [("local", 46, 53, 1, "local()", True, None)],
        )
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

    def assert_binding_context(self, language: str, template: str, name: str) -> None:
        for callback_text in CALLBACKS:
            source = template % callback_text
            native = process(source, ProcessConfig(language=language)).structure
            self.assert_binding_structure(source, language, name, callback_text, native)
            self.assert_binding_graph(source, language, name)

    def assert_binding_structure(self, source, language, name, callback_text, native):
        for existing in ([], native):
            self.assert_binding_item(source, language, name, callback_text, existing)

    def assert_binding_item(self, source, language, name, callback_text, existing):
        items = extract_structure(source.encode(), language, existing)
        self.assertEqual([item.name for item in items], [name])
        callback = items[0]
        self.assertEqual([child.name for child in callback.children], ["local"])
        start = source.index(callback_text)
        self.assertIsNotNone(callback.span)
        assert callback.span is not None
        self.assertEqual(
            (callback.span.start_byte, callback.span.end_byte),
            (start, start + len(callback_text)),
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
        for language, (template, name) in product(LANGUAGES, CONTEXTS):
            with self.subTest(language=language, context=template):
                self.assert_binding_context(language, template, name)

    def test_generator_ancestor_keeps_callback_and_local_call_owner(self) -> None:
        source = "function* outer() { const f = ((function* internal() { function local() {} yield local(); })); yield f(); }"
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
        tagged = extract_structure(source.encode(), language)
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
        for wrapper in wrappers:
            self.assert_wrapper_endpoints(
                source, language, name, callback_node, callback, local, wrapper
            )

    def assert_wrapper_endpoints(
        self, source, language, name, callback_node, callback, local, wrapper
    ):
        for start, end in (
            (wrapper, wrapper),
            (wrapper, callback_node),
            (callback_node, wrapper),
        ):
            self.assert_native_endpoint(
                source,
                language,
                name,
                callback_node,
                callback,
                local,
                (wrapper, start, end),
            )

    def assert_native_endpoint(
        self,
        source,
        language,
        name,
        callback_node,
        callback,
        local,
        endpoints,
    ):
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
        items = extract_structure(source.encode(), language, [native])
        self.assertEqual(len(items), 1)
        merged = items[0]
        self.assertEqual(merged.name, name)
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
        contexts = (*CONTEXTS, ("consume(((%s)));", "internal"))
        for language, (template, name) in product(LANGUAGES, contexts):
            with self.subTest(language=language, context=template):
                source = "/* café 😀 */\n" + template % CALLBACKS[1]
                self.assert_native_wrappers(source, language, name)

    def test_unresolved_binding_preserves_native_name_and_metadata_once(self) -> None:
        source = "consume((() => { function local() {} return local(); }));"
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_unresolved_binding(source, language)

    def assert_unresolved_binding(self, source, language):
        tagged = extract_structure(source.encode(), language)[0]
        native = replace(
            tagged,
            name="native callback",
            doc_comment="native docs",
            children=[],
        )
        items = extract_structure(
            source.encode(),
            language,
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
        source = """const f = (/* comment */ (() => 0));
const sequence = (0, (() => 0));
const invoked = ((() => 0))();
const choice = (ready ? (() => 0) : (() => 1));
consume(((function explicit() {})), ((function* generator() {})), (() => 0));
"""
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_transparent_parentheses(source, language)

    def assert_transparent_parentheses(self, source, language):
        items = extract_structure(source.encode(), language)
        self.assertEqual(
            [item.name for item in items],
            ["f", None, None, None, None, "explicit", "generator", None],
        )
        self.assertEqual(len(flatten(items)), 8)


if __name__ == "__main__":
    unittest.main()
