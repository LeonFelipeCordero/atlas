"""Expression identity, metadata ownership, and AST parentage on coffee modules."""

import unittest
from dataclasses import replace

from tree_sitter import Node
from tree_sitter_language_pack import ProcessConfig, StructureItem, process

from atlas.parsing.adapters import get_adapter
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_source


def flatten(items: list[StructureItem]) -> list[tuple[StructureItem, StructureItem | None]]:
    result = []
    stack: list[tuple[StructureItem, StructureItem | None]] = [(item, None) for item in reversed(items)]
    while stack:
        item, parent = stack.pop()
        result.append((item, parent))
        stack.extend(child_entries(item))
    return result


def child_entries(item: StructureItem) -> list[tuple[StructureItem, StructureItem]]:
    return [(child, item) for child in reversed(item.children)]


# Counts include all expression callables in the complete file, not function types.
# Nested indices identify real callback-in-callback ownership in source order.
APPLICATIONS = (
    ("java", "reporting/SalesReport.java", ["include", None, None, None, None, None, None], 10, (4, 5), "discounts"),
    ("kotlin", "reporting/SalesReport.kt", [None] * 8, 14, (3, 4), "discounts"),
    ("go", "reporting/Dispatch.go", ["DispatchReady", "ready", "label", "archive", None, None, "normalize"], 9, (5, 6), "DispatchReceipts"),
    ("rust", "brewing/inventory.rs", [None] * 4, 9, (2, 3), "restock"),
    ("javascript", "ordering/Orders.js", ["priceOrder", None, None, "createOrder", "drinkTickets", "pickupQueue", None, None], 11, (6, 7), "groupTickets"),
    ("typescript", "ordering/Orders.ts", ["priceOrder", None, None, "createOrder", "drinkTickets", "pickupQueue", None, None], 15, (6, 7), "groupTickets"),
    ("elixir", "reporting/Dispatch.ex", [None] * 5, 7, (3, 4), "receipts"),
    ("python", "src/coffee/reporting/sales.py", [None] * 3, 8, (1, 2), "discounts"),
)


class CallbackDeclarationTests(unittest.TestCase):
    def assert_callback_carriers(
        self, syntax: ParsedSyntax, items: list[StructureItem], count: int,
    ) -> list[tuple[StructureItem, StructureItem | None]]:
        root = syntax.tree()
        self.assertFalse(root.has_error)
        callback_types = get_adapter(syntax.source.language).callback_types
        expression_nodes = [node for node in walk(root) if node.type in callback_types]
        self.assertEqual(len(expression_nodes), count)
        declarations = self.assert_declaration_nodes(syntax, items)
        by_span = {(node.start_byte, node.end_byte): item for item, _, node in declarations}
        callbacks = [(item, parent) for item, parent, node in declarations if node.type in callback_types]
        self.assertEqual(len(callbacks), count)
        self.assert_callback_spans(callbacks, expression_nodes)
        self.assert_callback_parentage(root, callbacks, by_span)
        return callbacks

    def assert_declaration_nodes(self, syntax: ParsedSyntax, items: list[StructureItem]):
        declarations = []
        seen = set()
        for item, parent in flatten(items):
            node = self.assert_declaration_node(syntax, item)
            key = (node.start_byte, node.end_byte)
            self.assertNotIn(key, seen)
            seen.add(key)
            declarations.append((item, parent, node))
        return declarations

    def assert_declaration_node(self, syntax: ParsedSyntax, item: StructureItem) -> Node:
        span = item.span
        assert span is not None
        node = syntax.tree().descendant_for_byte_range(span.start_byte, span.end_byte - 1)
        assert node is not None
        self.assertEqual((node.start_byte, node.end_byte), (span.start_byte, span.end_byte))
        self.assertTrue(item.signature)
        self.assertTrue(syntax.source.source[span.start_byte:span.end_byte].decode().startswith(item.signature or ""))
        return node

    def assert_callback_spans(self, callbacks, expression_nodes):
        self.assertEqual(
            {(item.span.start_byte, item.span.end_byte) for item, _ in callbacks if item.span},
            {(node.start_byte, node.end_byte) for node in expression_nodes},
        )
        self.assertEqual([item.span.start_byte for item, _ in callbacks if item.span],
                         sorted(node.start_byte for node in expression_nodes))

    def assert_callback_parentage(self, root, callbacks, by_span):
        for callback, parent in callbacks:
            self.assertEqual(str(callback.kind).lower(), "function")
            assert callback.span is not None
            node = root.descendant_for_byte_range(callback.span.start_byte, callback.span.end_byte - 1)
            assert node is not None
            self.assertIs(parent, self.nearest_declaration(node, by_span))

    @staticmethod
    def nearest_declaration(node: Node, by_span: dict[tuple[int, int], StructureItem]):
        ancestor = node.parent
        while ancestor is not None:
            key = (ancestor.start_byte, ancestor.end_byte)
            declaration = by_span.get(key)
            if declaration is not None and key != (node.start_byte, node.end_byte):
                return declaration
            ancestor = ancestor.parent
        return None

    def test_nested_callbacks_match_real_ast_and_parentage_with_or_without_native(self):
        for application in APPLICATIONS:
            self.assert_application_callbacks(application)

    def assert_application_callbacks(self, application):
        language, path, *_ = application
        source = coffee_source(language, path)
        syntax = ParsedSyntax(source)
        for native in ([], process(source.source.decode(), ProcessConfig(language=language)).structure):
            with self.subTest(language=language, native=bool(native)):
                self.assert_native_callbacks(syntax, native, application)

    def assert_native_callbacks(self, syntax, native, application):
        _, _, expected_names, callable_count, nested, owner = application
        original = repr(native)
        items = extract_structure(syntax, native)
        callbacks = self.assert_callback_carriers(syntax, items, len(expected_names))
        self.assertEqual([item.name for item, _ in callbacks], expected_names)
        self.assertEqual(sum(str(item.kind).lower() in {"function", "method"}
                             for item, _ in flatten(items)), callable_count)
        first, child = (callbacks[index] for index in nested)
        assert first[1] is not None
        self.assertEqual(first[1].name, owner)
        self.assertIs(child[1], first[0])
        self.assertEqual(repr(native), original)

    def test_native_duplicate_callback_metadata_merges_once_without_mutation(self):
        for application in APPLICATIONS:
            with self.subTest(language=application[0]):
                self.assert_duplicate_callback_metadata(application)

    def assert_duplicate_callback_metadata(self, application):
        language, path, expected_names, *_ = application
        source = coffee_source(language, path)
        syntax = ParsedSyntax(source)
        tagged = extract_structure(syntax)
        callback = self.assert_callback_carriers(syntax, tagged, len(expected_names))[0][0]
        native = process(source.source.decode(), ProcessConfig(language=language)).structure
        decorated = replace(callback, doc_comment="callback docs", decorators=["native annotation"], children=[])
        existing = [*native, replace(decorated, name=""), replace(decorated, name=None)]
        original = repr(existing)
        items = extract_structure(syntax, existing)
        callbacks = self.assert_callback_carriers(syntax, items, len(expected_names))
        self.assertEqual([item.name for item, _ in callbacks], expected_names)
        self.assertEqual(callbacks[0][0].doc_comment, "callback docs")
        self.assertEqual(callbacks[0][0].decorators, ["native annotation"])
        self.assertEqual(callbacks[0][0].signature, decorated.signature)
        self.assertEqual(callbacks[0][0].span, decorated.span)
        self.assertTrue(all(item.doc_comment != "callback docs" for item, _ in flatten(items)
                            if item is not callbacks[0][0]))
        self.assertEqual(repr(existing), original)

    def test_unbound_callback_identity_ignores_conflicting_native_names(self):
        source = coffee_source("javascript", "ordering/Orders.js")
        syntax = ParsedSyntax(source)
        tagged = extract_structure(syntax)
        callback = self.assert_callback_carriers(syntax, tagged, 8)[6][0]
        native = process(source.source.decode(), ProcessConfig(language="javascript")).structure
        existing = [*native, replace(callback, name="stale-one", children=[]),
                    replace(callback, name="stale-two", children=[])]
        original = repr(existing)
        items = extract_structure(syntax, existing)
        callbacks = self.assert_callback_carriers(syntax, items, 8)
        # Native names remain metadata, never a second expression identity.
        self.assertEqual(callbacks[6][0].name, "stale-two")
        self.assertIs(callbacks[7][1], callbacks[6][0])
        self.assertEqual([item.name for item, _ in flatten(items)
                          if item.name in {"stale-one", "stale-two"}], ["stale-two"])
        self.assertEqual(repr(existing), original)

    def test_go_assigned_literal_accepts_safe_binding_not_receiver_assignment(self):
        syntax = ParsedSyntax(coffee_source("go", "reporting/Dispatch.go"))
        items = extract_structure(syntax)
        callbacks = self.assert_callback_carriers(syntax, items, 7)
        self.assertEqual([item.name for item, _ in callbacks], ["DispatchReady", "ready", "label", "archive", None, None, "normalize"])
        self.assertIsNone(callbacks[0][1])
        self.assertTrue(all(parent is items[3] for _, parent in callbacks[1:6]))
        self.assertIs(callbacks[6][1], callbacks[5][0])
        self.assertFalse(items[0].children)  # DispatchFilter is a type, not a callable.
        self.assertFalse(items[1].children)  # Notify's function type is not executable.

    def test_kotlin_anonymous_fun_and_labeled_lambda_not_wrappers(self):
        syntax = ParsedSyntax(coffee_source("kotlin", "reporting/Dispatch.kt"))
        items = extract_structure(syntax)
        callbacks = self.assert_callback_carriers(syntax, items, 4)
        deliver = items[2].children[1]
        self.assertEqual(deliver.name, "deliver")
        self.assertTrue(all(item.name is None for item, _ in callbacks))
        self.assertTrue(all(callbacks[index][1] is deliver for index in (0, 1, 3)))
        self.assertEqual(callbacks[2][1].name if callbacks[2][1] else None, "formatReady")
        self.assertFalse(items[1].children)  # DispatchFormatter is only a typealias.

    def test_elixir_multiclause_fn_and_identical_expressions_stay_distinct(self):
        source = coffee_source("elixir", "reporting/Dispatch.ex")
        syntax = ParsedSyntax(source)
        native = process(source.source.decode(), ProcessConfig(language="elixir")).structure
        items = extract_structure(syntax, native)
        callbacks = self.assert_callback_carriers(syntax, items, 5)
        self.assertTrue(all(parent is items[0].children[0] for _, parent in callbacks[:4]))
        self.assertEqual(callbacks[1][0].signature, callbacks[2][0].signature)
        self.assertNotEqual(callbacks[1][0].span, callbacks[2][0].span)
        self.assertFalse(callbacks[0][0].children)  # Two clauses form one fn carrier.
        self.assertIs(callbacks[4][1], callbacks[3][0])

    def test_script_bindings_and_inline_functions_keep_single_identity(self):
        source = coffee_source("javascript", "ordering/Dispatch.js")
        for language in ("javascript", "typescript", "tsx"):
            with self.subTest(language=language):
                self.assert_script_bindings(ParsedSyntax(replace(source, language=language)))

    def assert_script_bindings(self, syntax: ParsedSyntax):
        source = syntax.source
        native = process(source.source.decode(), ProcessConfig(language=source.language)).structure
        original = repr(native)
        items = extract_structure(syntax, native)
        callbacks = self.assert_callback_carriers(syntax, items, 12)
        self.assertEqual([item.name for item in items], ["dispatchLabel", "dispatchTickets", "Dispatch"])
        self.assertEqual([item.name for item, _ in callbacks], [
            "dispatchLabel", "dispatchTickets", "notify", "archive", None, None,
            None, None, None, "dispatchTotal", None, None,
        ])
        schedule = next(item for item in items[2].children if item.name == "schedule")
        self.assertEqual([item.name for item in schedule.children], [None, None, None, None, "dispatchTotal", None])
        self.assertEqual(schedule.children[0].children[0].name, "ticketLabel")
        self.assertEqual(repr(native), original)

    def test_declarations_inside_callbacks_keep_expression_parent(self):
        for language, path, count, callback_index, local_name in [
            ("javascript", "ordering/Dispatch.js", 12, 4, "ticketLabel"),
            ("kotlin", "reporting/Dispatch.kt", 4, 1, "formatReady"),
            ("rust", "Dispatch.rs", 2, 1, "label"),
        ]:
            with self.subTest(language=language):
                syntax = ParsedSyntax(coffee_source(language, path))
                items = extract_structure(syntax)
                callback = self.assert_callback_carriers(syntax, items, count)[callback_index][0]
                self.assertEqual(callback.children[0].name, local_name)
                self.assertEqual(str(callback.children[0].kind).lower(), "function")


if __name__ == "__main__":
    unittest.main()
