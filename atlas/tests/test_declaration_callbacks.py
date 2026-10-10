"""Real expression callables, native metadata identity, and AST parentage."""

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
    "java": """class Owner { static void outer(boolean ready) {
      if (ready) ping();
      use(x -> { if (x > 0) ping(); use(y -> y > 0 && ready ? 1 : 0); return x; });
    } }""",
    "kotlin": """fun outer(ready: Boolean) {
      if (ready) ping()
      use { x -> if (x > 0) ping(); use { y -> if (y > 0 && ready) 1 else 0 }; x }
    }""",
    "go": """package sample
    func outer(ready bool) {
      if ready { ping() }
      use(func(x int) int {
        if x > 0 { ping() }
        use(func(y int) int { if y > 0 && ready { return 1 }; return 0 })
        return x
      })
    }""",
    "rust": """fn outer(ready: bool) {
      if ready { ping(); }
      consume(|x: i32| {
        if x > 0 { ping(); }
        consume(|y: i32| if y > 0 && ready { 1 } else { 0 }); x
      });
    }""",
    "javascript": """function outer(ready) {
      if (ready) ping();
      use(x => { if (x > 0) ping(); use(y => y > 0 && ready ? 1 : 0); return x; });
    }""",
    "typescript": """function outer(ready: boolean) {
      if (ready) ping();
      use((x: number) => { if (x > 0) ping(); use((y: number) => y > 0 && ready ? 1 : 0); return x; });
    }""",
    "elixir": """defmodule Owner do
      def outer(ready) do
        if ready, do: ping()
        use(fn x ->
          if x > 0, do: ping()
          use(fn y -> if y > 0 and ready, do: 1, else: 0 end)
          x
        end)
      end
    end""",
    "python": """def outer(ready):
    if ready:
        ping()
    use(lambda x: (use(lambda y: 1 if y > 0 and ready else 0), 1 if x else 0))
""",
}
BOUND_SOURCES = {
    "java": "class Owner { java.util.function.IntUnaryOperator field = x -> x; void outer() { use(x -> x); } }",
    "kotlin": "typealias Callback = (Int) -> Int\nval top: Callback = { x -> x }\nfun outer(cb: Callback) { use { x -> x } }",
    "go": "package sample\ntype Callback func(int) int\nvar top Callback = func(x int) int { return x }\nfunc outer(cb Callback) { use(func(x int) int { return x }) }",
    "rust": "type Callback = fn(i32) -> i32; const TOP: Callback = |x| x; fn outer(cb: Callback) { consume(|x: i32| x); }",
    "typescript": "type Callback = (x: number) => number; const top: Callback = x => x; function outer(cb: Callback) { use((x: number) => x); }",
    "elixir": "top = fn x -> x end\ndefmodule Owner do\n def outer(cb), do: use(fn x -> x end)\nend",
    "python": "from typing import Callable\ntop = lambda x: x\ndef outer(cb: Callable[[int], int]):\n return lambda x: x\n",
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
        source = "function outer() { use(x => x + 1); }"
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
        source = """package sample
func outer() {
  accept := func(x int) bool { return x > 0 }
  left, right := func() {}, func() {}
  object.run = func() {}
  use(func() {})
}
"""
        items = extract_structure(parsing_syntax(source, "go"))
        callbacks = self.assert_callback_carriers(parsing_syntax(source, "go"), items, 5)
        self.assertEqual(
            [item.name for item, _ in callbacks],
            ["accept", "left", "right", None, None],
        )
        self.assertTrue(all(parent is items[0] for _, parent in callbacks))

    def test_kotlin_anonymous_fun_and_labeled_lambda_not_wrappers(self) -> None:
        source = """typealias Callback = (Int) -> Int
fun outer(cb: (Int) -> Int) {
  val assigned = fun(x: Int): Int { return if (x > 0) x else 0 }
  use(fun(x: Int) = if (x > 0) x else 0)
  use label@ { x -> if (x > 0) x else 0 }
}"""
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
        source = """defmodule Owner do
  def outer do
    use(fn x when x > 0 -> if x > 1, do: 1, else: 0; _ -> 0 end)
    use(fn x -> x end)
    use(fn x -> x end)
  end
end"""
        native = process(source, ProcessConfig(language="elixir")).structure
        items = extract_structure(parsing_syntax(source, "elixir"), native)
        callbacks = self.assert_callback_carriers(parsing_syntax(source, "elixir"), items, 3)
        self.assertTrue(all(parent is items[0].children[0] for _, parent in callbacks))

    def test_script_bindings_and_inline_functions_keep_single_identity(self) -> None:
        source = """const named = () => 0;
const generator = function* internal() { yield 1; };
object.action = function () {};
const holder = { apply: function* () {} };
function outer() { use(() => 0, function () {}, function* () {}, function local() {}); return function () {}; }
"""
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
            "javascript": "function outer() { use(() => { function local() {} return local(); }); }",
            "kotlin": "fun outer() { use { fun local() = 1; local() } }",
            "rust": "fn outer() { consume(|| { fn local() {} local(); }); }",
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
