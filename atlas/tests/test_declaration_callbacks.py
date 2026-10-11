"""Real expression callables, native metadata identity, and AST parentage."""

from tests.source_snapshot_fixture import case_text

import unittest
from dataclasses import replace

from tree_sitter import Node
from tree_sitter_language_pack import ProcessConfig, StructureItem, process

from atlas.parsing.adapters import get_adapter
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.parsing_fixture import parsing_syntax


def flatten(
    items: list[StructureItem],
) -> list[tuple[StructureItem, StructureItem | None]]:
    result = []
    stack: list[tuple[StructureItem, StructureItem | None]] = [
        (item, None) for item in reversed(items)
    ]
    while stack:
        item, parent = stack.pop()
        result.append((item, parent))
        stack.extend(child_entries(item))
    return result


def child_entries(item: StructureItem):
    return [(child, item) for child in reversed(item.children)]


def walk(root: Node) -> list[Node]:
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.named_children))
    return result


NESTED_SOURCES = {
    "java": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-java', 'sample.java'),
    "kotlin": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-kotlin', 'sample.kt'),
    "go": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-go', 'sample.go'),
    "rust": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-rust', 'sample.rs'),
    "javascript": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-javascript', 'sample.js'),
    "typescript": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-typescript', 'sample.ts'),
    "elixir": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-elixir', 'sample.ex'),
    "python": case_text('parsing', 'declaration_callbacks-nested_callbacks_match_real_ast_and_parentage_with_or_without_native-python', 'sample.py'),
}
BOUND_SOURCES = {
    "java": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-java', 'sample.java'),
    "kotlin": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-kotlin', 'sample.kt'),
    "go": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-go', 'sample.go'),
    "rust": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-rust', 'sample.rs'),
    "typescript": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-typescript', 'sample.ts'),
    "elixir": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-elixir', 'sample.ex'),
    "python": case_text('parsing', 'declaration_callbacks-bound_expressions_not_function_type_nodes-python', 'sample.py'),
}


class CallbackDeclarationTests(unittest.TestCase):
    def assert_callback_carriers(
        self, syntax: ParsedSyntax, items: list[StructureItem], count: int
    ) -> list[tuple[StructureItem, StructureItem | None]]:
        language = syntax.source.language
        root = syntax.tree()
        expression_nodes = [
            node
            for node in walk(root)
            if node.type in get_adapter(language).callback_types
        ]
        self.assertEqual(len(expression_nodes), count)
        entries = flatten(items)
        callbacks = []
        by_span = {}
        for item, parent in entries:
            span = item.span
            assert span is not None
            key = (span.start_byte, span.end_byte, item.name)
            self.assertNotIn(key, by_span)
            by_span[key] = item
            node = root.descendant_for_byte_range(span.start_byte, span.end_byte - 1)
            assert node is not None
            self.assertEqual(
                (node.start_byte, node.end_byte), (span.start_byte, span.end_byte)
            )
            if node.type in get_adapter(language).callback_types:
                self.assertEqual(str(item.kind).lower(), "function")
                callbacks.append((item, parent))
        self.assertEqual(len(callbacks), count)
        self.assertEqual(
            {
                (item.span.start_byte, item.span.end_byte)
                for item, _ in callbacks
                if item.span
            },
            {(node.start_byte, node.end_byte) for node in expression_nodes},
        )
        return callbacks

    def test_nested_callbacks_match_real_ast_and_parentage_with_or_without_native(
        self,
    ) -> None:
        for language, source in NESTED_SOURCES.items():
            self.assert_nested_callback_variants(source, language)

    def assert_nested_callback_variants(self, source, language):
        for native in (
            [],
            process(source, ProcessConfig(language=language)).structure,
        ):
            with self.subTest(language=language, native=bool(native)):
                items = extract_structure(parsing_syntax(source, language), native)
                first, nested = self.assert_callback_carriers(
                    parsing_syntax(source, language), items, 2
                )
                self.assertIsNotNone(first[1])
                assert first[1] is not None
                self.assertEqual(first[1].name, "outer")
                self.assertIs(nested[1], first[0])
                self.assertEqual([first[0].name, nested[0].name], [None, None])

    def test_bound_expressions_not_function_type_nodes(self) -> None:
        for language, source in BOUND_SOURCES.items():
            with self.subTest(language=language):
                self.assert_bound_expressions(source, language)

    def assert_bound_expressions(self, source, language):
        native = process(source, ProcessConfig(language=language)).structure
        items = extract_structure(parsing_syntax(source, language), native)
        callbacks = self.assert_callback_carriers(parsing_syntax(source, language), items, 2)
        expected_name = {"java": "field", "typescript": "top", "go": "top"}.get(
            language
        )
        self.assertEqual(callbacks[0][0].name, expected_name)
        self.assertIsNone(callbacks[1][0].name)
        self.assertIsNotNone(callbacks[1][1])
        assert callbacks[1][1] is not None
        self.assertEqual(callbacks[1][1].name, "outer")
        callables = [
            item
            for item, _ in flatten(items)
            if str(item.kind).lower() in {"function", "method"}
        ]
        self.assertEqual(len(callables), 3)

    def test_native_duplicate_callback_metadata_merges_once_without_mutation(
        self,
    ) -> None:
        for language, source in BOUND_SOURCES.items():
            with self.subTest(language=language):
                tagged = extract_structure(parsing_syntax(source, language))
                callback = self.assert_callback_carriers(parsing_syntax(source, language), tagged, 2)[
                    0
                ][0]
                native = process(source, ProcessConfig(language=language)).structure
                decorated = replace(
                    callback,
                    doc_comment="callback docs",
                    decorators=["native annotation"],
                    children=[],
                )
                existing = [
                    *native,
                    replace(decorated, name=""),
                    replace(decorated, name=None),
                ]
                original = repr(existing)
                items = extract_structure(parsing_syntax(source, language), existing)
                callbacks = self.assert_callback_carriers(parsing_syntax(source, language), items, 2)
                self.assertEqual(callbacks[0][0].doc_comment, "callback docs")
                self.assertEqual(callbacks[0][0].decorators, ["native annotation"])
                self.assertEqual(repr(existing), original)

    def test_unbound_callback_identity_ignores_conflicting_native_names(self) -> None:
        source = case_text('parsing', 'declaration_callbacks-unbound_callback_identity_ignores_conflicting_native_names-javascript', 'sample.js')
        callback = self.assert_callback_carriers(
            parsing_syntax(source, "javascript"), extract_structure(parsing_syntax(source, "javascript")), 1
        )[0][0]
        native = [
            replace(callback, name="stale-one", children=[]),
            replace(callback, name="stale-two", children=[]),
        ]
        items = extract_structure(parsing_syntax(source, "javascript"), native)
        self.assert_callback_carriers(parsing_syntax(source, "javascript"), items, 1)

    def test_go_assigned_literal_accepts_safe_binding_not_receiver_assignment(
        self,
    ) -> None:
        source = case_text('parsing', 'declaration_callbacks-go_assigned_literal_accepts_safe_binding_not_receiver_assignment-go', 'sample.go')
        items = extract_structure(parsing_syntax(source, "go"))
        callbacks = self.assert_callback_carriers(parsing_syntax(source, "go"), items, 5)
        self.assertEqual(
            [item.name for item, _ in callbacks],
            ["accept", "left", "right", None, None],
        )
        self.assertTrue(all(parent is items[0] for _, parent in callbacks))

    def test_kotlin_anonymous_fun_and_labeled_lambda_not_wrappers(self) -> None:
        source = case_text('parsing', 'declaration_callbacks-kotlin_anonymous_fun_and_labeled_lambda_not_wrappers-kotlin', 'sample.kt')
        items = extract_structure(parsing_syntax(source, "kotlin"))
        callbacks = self.assert_callback_carriers(parsing_syntax(source, "kotlin"), items, 3)
        self.assertTrue(
            all(
                item.name is None and parent.name == "outer"
                for item, parent in callbacks
                if parent
            )
        )

    def test_elixir_multiclause_fn_and_identical_expressions_stay_distinct(
        self,
    ) -> None:
        source = case_text('parsing', 'declaration_callbacks-elixir_multiclause_fn_and_identical_expressions_stay_distinct-elixir', 'sample.ex')
        native = process(source, ProcessConfig(language="elixir")).structure
        items = extract_structure(parsing_syntax(source, "elixir"), native)
        callbacks = self.assert_callback_carriers(parsing_syntax(source, "elixir"), items, 3)
        self.assertTrue(all(parent is items[0].children[0] for _, parent in callbacks))

    def test_script_bindings_and_inline_functions_keep_single_identity(self) -> None:
        source = case_text('parsing', 'declaration_callbacks-script_bindings_and_inline_functions_keep_single_identity-javascript', 'sample.js')
        for language in ("javascript", "typescript", "tsx"):
            with self.subTest(language=language):
                self.assert_script_bindings(source, language)

    def assert_script_bindings(self, source, language):
        native = process(source, ProcessConfig(language=language)).structure
        items = extract_structure(parsing_syntax(source, language), native)
        self.assert_callback_carriers(parsing_syntax(source, language), items, 9)
        self.assertEqual(
            [item.name for item in items],
            ["named", "generator", "action", "apply", "outer"],
        )
        self.assertEqual(
            [item.name for item in items[-1].children],
            [None, None, None, "local", None],
        )

    def test_declarations_inside_callbacks_keep_expression_parent(self) -> None:
        samples = {
            "javascript": case_text('parsing', 'declaration_callbacks-declarations_inside_callbacks_keep_expression_parent-javascript', 'sample.js'),
            "kotlin": case_text('parsing', 'declaration_callbacks-declarations_inside_callbacks_keep_expression_parent-kotlin', 'sample.kt'),
            "rust": case_text('parsing', 'declaration_callbacks-declarations_inside_callbacks_keep_expression_parent-rust', 'sample.rs'),
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                items = extract_structure(parsing_syntax(source, language))
                callback = self.assert_callback_carriers(parsing_syntax(source, language), items, 1)[0][
                    0
                ]
                self.assertEqual(callback.children[0].name, "local")


if __name__ == "__main__":
    unittest.main()
