"""Extraction policies on whole application sources, independent of resolution."""

import unittest
from dataclasses import replace

from atlas.parsing.adapters import DEFAULT_ADAPTER, get_adapter
from atlas.parsing.parser import parse_file
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import DeclarationHeader, ParsedSyntax
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_source


class ExtractionAdapterTest(unittest.TestCase):
    def test_per_language_inheritance_and_generic_fallback(self):
        for language, path, name, expected in [
            ("java", "inventory/Inventory.java", "Inventory", ["StockLedger", "Reservable"]),
            ("kotlin", "inventory/Inventory.kt", "Inventory", ["StockLedger", "Reservable"]),
            ("typescript", "ordering/Dispatch.ts", "Dispatch", ["Receipt", "Iterable"]),
            ("typescript", "ordering/Dispatch.ts", "DispatchBook", ["orderTypes.OrderBook", "Iterable"]),
            ("python", "src/coffee/orders/service.py", "OrderService", ["CoffeeOrders", "AuditTrail"]),
            ("python", "src/coffee/inventory/stock.py", "Ledger", ["ABC", "Generic"]),
            ("python", "src/coffee/inventory/stock.py", "Inventory", ["Ledger"]),
            ("javascript", "brewing/Brewer.js", "Brewer", ["Brewing"]),
        ]:
            with self.subTest(language=language, declaration=name):
                self.assert_inheritance(coffee_source(language, path), (name, expected))
        self.assertIs(get_adapter("ruby"), DEFAULT_ADAPTER)
        source = coffee_source("ruby", "reporting/Dispatch.rb")
        dispatcher = extract_structure(ParsedSyntax(source))[0].children[0].children[0]
        self.assertEqual(DEFAULT_ADAPTER.inheritance(DeclarationHeader("ruby", "class", dispatcher.signature or "")), [])

    def assert_inheritance(self, source, expectation):
        name, expected = expectation
        items = extract_structure(ParsedSyntax(source))
        declaration = next(item for item in items if item.name == name)
        header = DeclarationHeader(source.language, str(declaration.kind).lower(), declaration.signature or "")
        self.assertEqual(get_adapter(source.language).inheritance(header), expected)

    def test_jsx_tag_name_sites_are_references_without_swallowing_attribute_calls(self):
        source = coffee_source("javascript", "ordering/DispatchView.jsx")
        for language in ("javascript", "tsx"):
            with self.subTest(language=language):
                self.assert_jsx_calls(replace(source, language=language))

    def assert_jsx_calls(self, source):
        parsed = parse_file(source)
        self.assertIsNone(parsed.parse_error)
        self.assertEqual(
            [(call.evidence, call.relationship, call.qualifier) for call in parsed.calls],
            [
                ("ReceiptCard", "REFERENCES", None),
                ("dispatchLabel(order)", "CALLS", None),
                ("DispatchCards.ReceiptCard", "REFERENCES", "DispatchCards"),
                ("new Dispatch()", "CALLS", None),
                ("dispatcher.schedule([order])", "CALLS", "dispatcher"),
            ],
        )
        for call in parsed.calls:
            self.assertEqual(source.source[call.start_byte:call.end_byte].decode(), call.evidence)
            self.assertEqual(call.end_byte - call.start_byte, len(call.evidence.encode()))

    def test_decorators_visibility_and_import_supplement_owned_by_adapters(self):
        for language, path, node_type, visibility, decorators in [
            ("java", "reporting/Dispatch.java", "class_declaration", "public", ["@Deprecated"]),
            ("rust", "Dispatch.rs", "struct_item", None, []),
        ]:
            with self.subTest(language=language):
                self.assert_declaration_metadata(
                    ParsedSyntax(coffee_source(language, path)), (node_type, visibility, decorators),
                )
        for language, path, expected in [
            ("kotlin", "orders/OrderService.kt", [
                ("import coffee.brewing.Brewer as CoffeeBrewer", 3),
                ("import coffee.inventory.Inventory", 4),
            ]),
            ("rust", "Dispatch.rs", [("mod dispatch_report;", 2)]),
        ]:
            with self.subTest(language=language):
                syntax = ParsedSyntax(coffee_source(language, path))
                native = expected[:1]
                original = native.copy()
                self.assertEqual(get_adapter(language).imports(syntax, native), expected)
                self.assertEqual(native, original)

    def assert_declaration_metadata(self, syntax, expectation):
        node_type, visibility, decorators = expectation
        node = next(node for node in walk(syntax.tree()) if node.type == node_type)
        self.assertEqual(get_adapter(syntax.source.language).metadata(node), (visibility, decorators))

    def test_rust_macro_payload_remains_rust_only(self):
        syntax = ParsedSyntax(coffee_source("rust", "Dispatch.rs"))
        rust = get_adapter("rust")
        sites = list(rust.call_sites(syntax.tree()))
        self.assertEqual([rust.normalize_call(site)[0] for site in sites], [
            "format!", "collect", "map", "filter", "iter", "portions", "pickup", "encode",
            "label", "preview", "receipts", "println!", "pickup", "send",
        ])
        self.assertEqual([site[2] for site in sites], [False] * 12 + [True, False])
        macro_call = sites[12]
        node, offset, opaque, parents = macro_call
        self.assertTrue(opaque)
        self.assertEqual(parents, ())
        self.assertEqual(syntax.source.source[node.start_byte + offset:node.end_byte + offset],
                         b"dispatch_labels::pickup(&receipt)")
        python = get_adapter("python")
        self.assertFalse(any(site[2] for site in python.call_sites(syntax.tree())))
        python_syntax = ParsedSyntax(coffee_source("python", "src/coffee/reporting/dispatch.py"))
        self.assertTrue(extract_structure(python_syntax))
        self.assertFalse(any(site[2] for site in python.call_sites(python_syntax.tree())))


if __name__ == "__main__":
    unittest.main()
