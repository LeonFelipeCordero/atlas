import unittest
from dataclasses import replace
from unittest.mock import patch

from tree_sitter_language_pack import ProcessConfig, get_tags_query, process

from atlas.parsing.structure import _declaration_query, extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_consolidation import coffee_source
from tests.parsing_fixture import parsing_syntax
from tests.source_snapshot_fixture import case_bytes


def names(items):
    return [item.name for item in items]


class StructureTagsTest(unittest.TestCase):
    def setUp(self) -> None:
        _declaration_query.cache_clear()

    def tearDown(self) -> None:
        _declaration_query.cache_clear()

    def test_uses_bundled_tags_with_graph_metadata_and_nesting(self) -> None:
        source = coffee_source("kotlin", "orders/OrderService.kt")
        with patch("atlas.parsing.structure.get_tags_query", wraps=get_tags_query) as tags:
            structure = extract_structure(ParsedSyntax(source))
            tags.assert_called_once_with("kotlin")
        self.assertEqual(names(structure), ["coffee.orders", "CoffeeOrders", "OrderService"])
        service = structure[2]
        self.assertEqual(names(service.children), [
            None, "place", "place", "fulfill", "preview", "receipts", "notify", "place", "Companion",
        ])
        receipts = service.children[5]
        self.assertEqual(names(receipts.children), [None, "formatReady"])
        deprecated = service.children[7]
        self.assertEqual(deprecated.decorators, [
            '@Deprecated("Use place with OrderLine for explicit quantity and price")',
        ])
        span = deprecated.span
        assert span is not None
        self.assertEqual((span.start_line, span.end_line), (48, 49))
        self.assertEqual(source.source[span.start_byte:span.end_byte].decode(), deprecated.signature)
        companion = service.children[8]
        self.assertEqual(companion.kind, "class")
        self.assertEqual(names(companion.children), ["stocked"])
        order_types = extract_structure(ParsedSyntax(coffee_source("kotlin", "orders/Order.kt")))
        factory = order_types[2].children[1]
        self.assertEqual(factory.name, "Factory")
        self.assertEqual(factory.kind, "class")
        self.assertEqual(names(factory.children), ["espresso"])

    def test_kotlin_private_visibility_discriminator(self) -> None:
        # Coffee services expose public operations; private callable visibility is
        # deliberately retained independently rather than dropping that assertion.
        source = case_bytes('parsing', 'structure-uses_bundled_tags_with_graph_metadata_and_nesting-kotlin', 'sample.kt')
        service = extract_structure(parsing_syntax(source, "kotlin"))[1]
        self.assertEqual(service.children[0].visibility, "private")

    def test_unnamed_companion_is_a_container_without_duplicate_declarations(self) -> None:
        source = coffee_source("kotlin", "inventory/Inventory.kt")
        structure = extract_structure(ParsedSyntax(source))
        self.assertEqual(names(structure), ["coffee.inventory", "StockLedger", "Reservable", "Inventory"])
        inventory = structure[3]
        self.assertEqual(names(inventory.children), [
            "Change", "record", "receive", "reserve", "units", "Companion",
        ])
        self.assertEqual(names(inventory.children[-1].children), ["stocked"])
        self.assertEqual(sum(child.name == "Companion" for child in inventory.children), 1)

    def test_java_methods_constructors_overloads_and_nested_types(self) -> None:
        source = coffee_source("java", "orders/OrderService.java")
        native = process(source.source.decode(), ProcessConfig(language="java")).structure
        original = repr(native)
        structure = extract_structure(ParsedSyntax(source), native)
        self.assertEqual(names(structure), ["coffee.orders", "OrderService"])
        service = structure[1]
        self.assertEqual(names(service.children), [
            "audit", "OrderService", "OrderService", "place", "place", "fulfill",
            "preview", "orders", "place", "stocked", "Factory",
        ])
        self.assertEqual([str(child.kind).lower() for child in service.children[1:3]],
                         ["constructor", "constructor"])
        self.assertEqual(service.children[8].visibility, "public")
        self.assertEqual(service.children[8].decorators, ["@Deprecated"])
        self.assertEqual(names(service.children[-1].children), ["Factory", "create"])
        self.assertEqual(service.signature, native[1].signature)
        self.assertEqual(repr(native), original)
        contract = extract_structure(ParsedSyntax(coffee_source("java", "orders/CoffeeOrders.java")))
        self.assertEqual(str(contract[1].kind).lower(), "interface")
        self.assertEqual(names(contract[1].children), ["fulfill", "ready"])

    def test_java_private_method_visibility_discriminator(self) -> None:
        # Coffee constructors are private, but its business methods are public.
        source = case_bytes('parsing', 'structure-java_methods_constructors_overloads_and_nested_types-java', 'sample.java')
        structure = extract_structure(parsing_syntax(source, "java"))
        self.assertEqual(structure[2].children[1].visibility, "private")

    def test_java_private_constructor_visibility(self) -> None:
        structure = extract_structure(ParsedSyntax(coffee_source("java", "brewing/Recipe.java")))
        constructor = structure[1].children[0]
        self.assertEqual(constructor.kind, "constructor")
        self.assertEqual(constructor.visibility, "private")

    def test_other_languages_use_the_same_nesting_and_keep_native_metadata(self) -> None:
        for language, path in (
            ("python", "src/coffee/orders/service.py"),
            ("typescript", "ordering/Orders.ts"),
        ):
            with self.subTest(language=language):
                source = coffee_source(language, path)
                native = process(source.source.decode(), ProcessConfig(language=language)).structure
                native[0].children[0] = replace(native[0].children[0], doc_comment="native operation docs")
                original = repr(native)
                structure = extract_structure(ParsedSyntax(source), native)
                self.assertEqual(structure[0].children[0].doc_comment, "native operation docs")
                self.assertEqual(repr(native), original)
                if language == "python":
                    self.assertEqual(names(structure), ["audited", "CoffeeOrders", "AuditTrail", "OrderService"])
                    wrapped = structure[0].children[0].children[0]
                    self.assertEqual(wrapped.name, "wrapped")
                    self.assertEqual(wrapped.decorators, ["@wraps(operation)"])
                    service = structure[3]
                    self.assertEqual(names(service.children[4].children), ["format_ready"])
                    self.assertEqual(service.children[6].decorators, [
                        "@staticmethod  # Delivery estimates do not depend on service state.",
                    ])
                else:
                    self.assertEqual(names(structure), [
                        "priceOrder", "createOrder", "drinkTickets", "pickupQueue",
                        "quote", "quote", "quote", "quoteWithFees", "groupTickets",
                    ])
                    self.assertEqual(names(structure[0].children), ["lineTotal", None, None])
                    self.assertEqual(names(structure[2].children), ["ticket"])

    def test_ruby_native_nesting_without_a_coffee_project(self) -> None:
        source = case_bytes('parsing', 'structure-other_languages_use_the_same_nesting_and_keep_native_metadata-ruby', 'sample.rb')
        native = process(source.decode(), ProcessConfig(language="ruby")).structure
        structure = extract_structure(parsing_syntax(source, "ruby"), native)
        self.assertEqual(names(structure), ["Demo"])
        self.assertEqual(names(structure[0].children), ["Service"])
        self.assertEqual(names(structure[0].children[0].children), ["run"])

    def test_missing_bundled_tags_preserves_native_extraction(self) -> None:
        source = case_bytes('parsing', 'structure-missing_bundled_tags_preserves_native_extraction-csharp', 'sample.cs')
        native = process(source.decode(), ProcessConfig(language="csharp")).structure
        with patch("atlas.parsing.structure.get_tags_query", return_value=None):
            self.assertIs(extract_structure(parsing_syntax(source, "csharp"), native), native)

    def test_queries_are_cached_per_language(self) -> None:
        with patch("atlas.parsing.structure.get_tags_query", wraps=get_tags_query) as tags:
            for language in ["kotlin", "java", "kotlin", "java"]:
                _declaration_query(language)
            self.assertEqual([call.args[0] for call in tags.call_args_list], ["kotlin", "java"])


if __name__ == "__main__":
    unittest.main()
