"""Canonical declaration identity and metadata on whole coffee modules."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from tree_sitter_language_pack import ProcessConfig, StructureItem, process

from atlas.domain.models import SourceFile
from atlas.parsing.structure import _declaration_query, extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_consolidation import coffee_source


def merged(source: SourceFile) -> list[StructureItem]:
    return extract_structure(
        ParsedSyntax(source),
        process(source.source.decode(), ProcessConfig(language=source.language)).structure,
    )


def names(items: list[StructureItem]) -> list[str | None]:
    return [item.name for item in items]


class CanonicalDeclarationTests(unittest.TestCase):
    def test_kotlin_unnamed_native_declarations_preserve_metadata(self) -> None:
        source = coffee_source("kotlin", "brewing/Recipe.kt")
        native = process(source.source.decode(), ProcessConfig(language="kotlin")).structure
        self.assertEqual(names(native), ["coffee.brewing", None, None])
        native[1] = replace(native[1], doc_comment="native docs", decorators=["native annotation"])
        original = repr(native)
        items = extract_structure(ParsedSyntax(source), native)
        self.assertEqual(names(items), ["coffee.brewing", "portions", "preview"])
        self.assertEqual(items[1].doc_comment, "native docs")
        self.assertEqual(items[1].decorators, ["native annotation"])
        self.assertEqual(items[1].signature, native[1].signature)
        self.assertEqual(repr(native), original)

    def test_kotlin_overloads_preserve_metadata_and_utf8_spans(self) -> None:
        source = coffee_source("kotlin", "reporting/SalesReport.kt")
        items = merged(source)
        self.assertEqual(names(items), ["coffee.reporting", "OrderFilter", "SalesReport"])
        methods = [item for item in items[2].children if item.name == "résumé"]
        self.assertEqual(len(methods), 2)
        self.assertNotEqual(methods[0].span, methods[1].span)
        for method in methods:
            span = method.span
            assert span is not None
            self.assertEqual(source.source[span.start_byte:span.end_byte].decode(), method.signature)
        self.assertEqual([(item.span.start_line, item.span.end_line) for item in methods if item.span],
                         [(38, 41), (43, 43)])
        # A real nested declaration remains attached to its enclosing callback.
        self.assertEqual(names(items[2].children[1].children[0].children), ["add"])

    def test_ts_interface_callable_properties_not_types_or_fields(self) -> None:
        source = coffee_source("typescript", "ordering/Order.ts")
        for language in ("typescript", "tsx"):
            with self.subTest(language=language):
                # The complete TypeScript coffee module is also valid TSX. This
                # changes the grammar, never the input bytes or declarations.
                self.assert_interface_properties(replace(source, language=language))

    def assert_interface_properties(self, source: SourceFile) -> None:
        items = merged(source)
        self.assertEqual(names(items), ["OrderItem", "Order", "Ticket", "OrderBook", "PricingContext", "OrderBookProvider"])
        self.assertFalse(items[0].children)
        self.assertFalse(items[1].children)
        self.assertFalse(items[2].children)
        self.assertFalse(items[4].children)
        # Provider constructor signatures and callbacks nested inside object
        # properties are types, not executable interface callables, in both grammars.
        self.assertFalse(items[5].children)
        children = items[3].children
        self.assertEqual(names(children), [
            "select", "onChange", '"daily-total"', "[Symbol.iterator]", "find", "find",
        ])
        self.assertTrue(all(str(item.kind).lower() == "method" and not item.children for item in children))
        for item in children:
            span = item.span
            assert span is not None
            self.assertEqual(source.source[span.start_byte:span.end_byte].decode(), item.signature)

    def test_java_constructor_kind_and_visibility(self) -> None:
        items = merged(coffee_source("java", "brewing/Recipe.java"))
        self.assertEqual(names(items), ["coffee.brewing", "Recipe"])
        self.assertEqual([str(item.kind).lower() for item in items[1].children],
                         ["constructor", "method", "method"])
        self.assertEqual(items[1].children[0].visibility, "private")
        service = merged(coffee_source("java", "orders/OrderService.java"))[1]
        constructors = [item for item in service.children if item.name == "OrderService"]
        self.assertEqual(len(constructors), 2)
        self.assertTrue(all(item.kind == "constructor" for item in constructors))
        self.assertNotEqual(constructors[0].span, constructors[1].span)

    def test_python_decorator_metadata_and_nested_definition(self) -> None:
        source = coffee_source("python", "src/coffee/orders/service.py")
        for items in (merged(source), extract_structure(ParsedSyntax(source))):
            self.assertEqual(items[1].children[0].decorators, ["@abstractmethod"])
            wrapped = items[0].children[0].children[0]
            self.assertEqual(wrapped.decorators, ["@wraps(operation)"])
            service = items[3]
            self.assertEqual(service.children[1].decorators, ['@audited("place")'])
            receipts = service.children[4]
            self.assertEqual(names(receipts.children), ["format_ready"])
            self.assertFalse(receipts.children[0].decorators)

    def test_python_stacked_utf8_decorator_discriminator(self) -> None:
        source = coffee_source("python", "src/coffee/reporting/dispatch.py")
        for items in (extract_structure(ParsedSyntax(source)), merged(source)):
            self.assert_stacked_decorators(source, items)

    def assert_stacked_decorators(self, source: SourceFile, items: list[StructureItem]) -> None:
        self.assertEqual(names(items), ["register", "annotate", "Dispatch"])
        self.assertEqual(items[2].decorators, ["@register('café')"])
        receipts = items[2].children[0]
        self.assertEqual(receipts.decorators, ["@staticmethod", "@annotate(level=1)"])
        self.assertEqual(names(receipts.children), ["format_ready"])
        self.assertFalse(receipts.children[0].decorators)
        for declaration in (items[2], receipts, receipts.children[0]):
            span = declaration.span
            assert span is not None
            self.assertTrue(declaration.signature)
            self.assertTrue(source.source[span.start_byte:span.end_byte].decode().startswith(declaration.signature or ""))

    def test_python_native_decorated_wrapper_canonicalizes_to_definition(self) -> None:
        source = coffee_source("python", "src/coffee/orders/models.py")
        native = process(source.source.decode(), ProcessConfig(language="python")).structure
        declaration = native[1]
        assert declaration.span is not None
        wrapper = replace(
            declaration,
            span=replace(declaration.span, start_byte=source.source.index(b"@dataclass(frozen=True)"),
                         start_line=10, start_column=0),
            doc_comment="class docs",
        )
        items = extract_structure(ParsedSyntax(source), [native[0], wrapper, native[2]])
        self.assertEqual(names(items), ["OrderStatus", "OrderLine", "Order"])
        self.assertEqual(items[1].span, declaration.span)
        self.assertEqual(items[1].decorators, ["@dataclass(frozen=True)"])
        self.assertEqual(items[1].doc_comment, "class docs")
        self.assertEqual(names(items[1].children), ["subtotal", "espresso"])

    def test_missing_tags_and_unrelated_native_languages(self) -> None:
        source = coffee_source("csharp", "reporting/Dispatch.cs")
        native = process(source.source.decode(), ProcessConfig(language="csharp")).structure
        self.assertEqual(names(native), ["Dispatch"])
        original = repr(native)
        _declaration_query.cache_clear()
        try:
            with patch("atlas.parsing.structure.get_tags_query", return_value=None):
                self.assertIs(extract_structure(ParsedSyntax(source), native), native)
                self.assertEqual(extract_structure(ParsedSyntax(source)), [])
                self.assertEqual(repr(native), original)
        finally:
            _declaration_query.cache_clear()
        items = merged(coffee_source("ruby", "reporting/Dispatch.rb"))
        self.assertEqual(names(items), ["Coffee"])
        self.assertEqual(names(items[0].children), ["Reporting"])
        dispatcher = items[0].children[0].children[0]
        self.assertEqual(dispatcher.name, "Dispatch")
        self.assertEqual(names(dispatcher.children), ["initialize", "deliver", "preview"])


if __name__ == "__main__":
    unittest.main()
