"""Source-derived complexity expectations, independent of graph snapshots."""

import unittest

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.extraction.complexity import calculate_complexity


class GrammarComplexityRegressionTests(unittest.TestCase):
    def parse(self, language: str, source: str) -> Node:
        root = get_parser(language).parse(source.encode()).root_node
        self.assertFalse(root.has_error, str(root))
        return root.named_children[0]

    def assert_metrics(
        self, node: Node, expected: tuple[int, int, int, int, int]
    ) -> None:
        self.assertEqual(calculate_complexity(node), Complexity(*expected))

    def measure(
        self, language: str, source: str, expected: tuple[int, int, int, int, int]
    ) -> None:
        self.assert_metrics(self.parse(language, source), expected)

    def test_kotlin_each_short_circuit_operator_without_boolean_depth(self) -> None:
        self.measure(
            "kotlin",
            "fun choose() { if (a && b || c && d) accept() }",
            (5, 0, 0, 5, 1),  # Entry, if, three operators.
        )
        self.measure(
            "kotlin",
            "fun scan() { while(active) { for(item in items) { "
            "if(item == first || item == last) accept() } } }",
            (5, 1, 1, 7, 3),
        )

    def test_python_refutable_match_patterns_and_fallbacks(self) -> None:
        self.measure(
            "python",
            "def route(value):\n match value:\n"
            "  case 0 | 1: pass\n"
            "  case State.READY: pass\n"
            "  case [first, *rest]: pass\n"
            "  case _: pass\n",
            (4, 0, 0, 4, 1),
        )
        fallbacks = ("_", "captured", "_ as captured", "(captured)", "0 | _")
        for pattern in fallbacks:
            with self.subTest(pattern=pattern):
                self.measure(
                    "python",
                    f"def route(value):\n match value:\n  case {pattern}: pass\n",
                    (1, 0, 0, 1, 0),
                )

    def test_python_fallback_guards_are_decisions(self) -> None:
        for pattern in ("_", "captured", "_ as captured"):
            with self.subTest(pattern=pattern):
                self.measure(
                    "python",
                    "def route(value):\n match value:\n"
                    f"  case {pattern} if ready and enabled: pass\n"
                    "  case _: pass\n",
                    (3, 0, 0, 3, 1),  # Guard and its conjunction, not the fallback.
                )

    def test_python_case_guard_depth_does_not_leak_into_body(self) -> None:
        self.measure(
            "python",
            "def route(value):\n if active:\n  match value:\n"
            "   case 1 if ready:\n    if enabled: accept()\n"
            "   case _:\n    if fallback: reject()\n",
            (6, 2, 0, 8, 3),
            # Active=1; case=2; guard/body-if=3; fallback body-if=2.
        )

    def test_python_match_nesting_and_nested_functions(self) -> None:
        self.measure(
            "python",
            "def scan(values):\n while active:\n  if enabled:\n"
            "   match value:\n    case 1:\n"
            "     if ready and valid: accept()\n"
            "     def inner():\n      for x in values:\n       if x: pass\n"
            "    case _: pass\n",
            (6, 2, 0, 8, 4),
        )

    def test_elixir_if_unless_and_qualified_non_controls(self) -> None:
        self.measure(
            "elixir",
            "def choose(x) do\n if x && ready do\n"
            " unless stopped || paused, do: accept(), else: reject()\n"
            " else\n fallback()\n end\n Client.if(x)\n Client.case(x)\nend",
            (5, 0, 0, 5, 2),
        )

    def test_elixir_case_and_cond_default_arm_exclusion(self) -> None:
        self.measure(
            "elixir",
            "def choose(x) do\n case x do\n"
            " true -> accept()\n false -> reject()\n _ -> fallback()\n end\nend",
            (3, 0, 0, 3, 1),  # Unlike cond, true is a refutable case pattern.
        )
        self.measure(
            "elixir",
            "def choose(x) do\n cond do\n"
            " x > 0 and ready -> if enabled, do: accept()\n"
            " x < 0 -> reject()\n true -> fallback()\n end\nend",
            (5, 0, 0, 5, 2),
        )

    def test_elixir_guarded_case_alternatives_and_deep_penalties(self) -> None:
        self.measure(
            "elixir",
            "def choose(x) do\n if enabled do\n unless stopped do\n"
            " case x do\n"
            " 1 when ready and valid -> if active, do: accept()\n"
            " _ -> fallback()\n end\n end\n end\nend",
            (7, 3, 0, 10, 4),
            # Case arm=3; guard=4; body if=4; boolean adds no depth.
        )
        self.measure(
            "elixir",
            "def choose(x) do\n case x do\n"
            " _ when ready -> accept()\n _ -> fallback()\n end\nend",
            (3, 0, 0, 3, 2),  # Guarded wildcard is not a default arm.
        )

    def test_elixir_declaration_and_lambda_guards(self) -> None:
        self.measure(
            "elixir",
            "def choose(x) when x > 0 and ready, do: unless(x > 10, do: accept())",
            (4, 0, 0, 4, 1),
        )
        self.measure(
            "elixir",
            "fn x when x > 0 -> if x and ready, do: accept(); "
            "_ -> unless stopped, do: reject() end",
            (5, 0, 0, 5, 1),  # Fn clauses are not case alternatives.
        )

    def test_elixir_reducer_calls_are_not_loops_and_fn_scopes_are_independent(
        self,
    ) -> None:
        node = self.parse(
            "elixir",
            "def aggregate(items) do\n"
            " Enum.reduce(items, 0, fn item, sum ->\n"
            "  unless stopped do\n"
            "   Enum.reduce(item, sum, fn value, acc ->\n"
            "    if value > 0 and ready, do: acc + value, else: acc\n"
            "   end)\n  end\n end)\nend",
        )
        self.assert_metrics(node, (1, 0, 0, 1, 0))
        stack = [node]
        callables = []
        while stack:
            child = stack.pop()
            if child.type == "anonymous_function":
                callables.append(child)
            stack.extend(reversed(child.named_children))
        self.assertEqual(len(callables), 2)
        self.assert_metrics(callables[0], (2, 0, 0, 2, 1))
        self.assert_metrics(callables[1], (3, 0, 0, 3, 1))

    def test_elixir_nested_declaration_scopes(self) -> None:
        for declaration in ("def inner(x)", "defp inner(x)", "defmacro inner(x)"):
            with self.subTest(declaration=declaration):
                self.measure(
                    "elixir",
                    "def outer(x) do\n if ready do\n"
                    f" {declaration}, do: if(x and enabled, do: accept())\n"
                    " end\n defmodule Inner do\n"
                    " def run(), do: unless(stopped, do: reject())\n end\nend",
                    (2, 0, 0, 2, 1),
                )

    def test_else_if_chains_share_depth_across_grammars(self) -> None:
        samples = {
            "typescript": "{if(a){}else if(b){}else if(c){if(d){}}}",
            "javascript": "{if(a){}else if(b){}else if(c){if(d){}}}",
            "java": "void f(){if(a){}else if(b){}else if(c){if(d){}}}",
            "kotlin": "fun f(){if(a){}else if(b){}else if(c){if(d){}}}",
            "go": "func f(){if a {} else if b {} else if c {if d {}}}",
            "rust": "fn f(){if a {} else if b {} else if c {if d {}}}",
            "python": "def f():\n if a: pass\n elif b: pass\n elif c:\n  if d: pass\n",
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.measure(language, source, (5, 0, 0, 5, 2))

    def test_default_arms_remain_excluded_across_grammars(self) -> None:
        samples = {
            "typescript": "{switch(x){case 1: accept(); break; default: reject();}}",
            "javascript": "{switch(x){case 1: accept(); break; default: reject();}}",
            "java": "void f(){switch(x){case 1: accept(); break; default: reject();}}",
            "kotlin": "fun f(x: Int){when(x){1 -> accept(); else -> reject()}}",
            "go": "func f(x int){switch x {case 1: accept(); default: reject()}}",
            "rust": "fn f(x: i32){match x {1 => accept(), _ => reject()};}",
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.measure(language, source, (2, 0, 0, 2, 1))

    def test_braced_else_is_real_nesting_not_else_if(self) -> None:
        for language, source in (
            ("kotlin", "fun f(){if(a){}else {if(b){if(c){}}}}"),
            ("typescript", "{if(a){}else {if(b){if(c){}}}}"),
        ):
            with self.subTest(language=language):
                self.measure(language, source, (4, 1, 0, 5, 3))

    def test_callable_roots_use_bodies_not_parameter_defaults(self) -> None:
        samples = {
            "python": "def choose(x=1 if ready else 0):\n if x: accept()\n",
            "typescript": "function choose(x = ready ? 1 : 0){if(x) accept()}",
            "kotlin": "fun choose(x: Int = if(ready) 1 else 0){if(x > 0) accept()}",
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.assert_callable_body_metrics(language, source)

    def assert_callable_body_metrics(self, language: str, source: str) -> None:
        node = self.parse(language, source)
        self.assert_metrics(node, (2, 0, 0, 2, 1))
        body = node.child_by_field_name("body")
        if body is None:
            body = next(c for c in node.named_children if c.type == "function_body")
        self.assert_metrics(body, (2, 0, 0, 2, 1))


if __name__ == "__main__":
    unittest.main()
