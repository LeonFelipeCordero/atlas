"""Grammar regressions measured on declarations from entire coffee files."""

import unittest

from tree_sitter import Node

from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity
from tests.coffee_consolidation import coffee_node


class GrammarComplexityRegressionTests(unittest.TestCase):
    def assert_metrics(
        self, node: Node, expected: tuple[int, int, int, int, int]
    ) -> None:
        self.assertEqual(calculate_complexity(node), Complexity(*expected))

    def assert_python(self, name: str, expected: tuple[int, int, int, int, int]) -> None:
        self.assert_metrics(coffee_node(
            "python", "src/coffee/orders/fulfillment.py", f"Fulfillment.{name}",
        ), expected)

    def assert_elixir(self, name: str, expected: tuple[int, int, int, int, int]) -> None:
        self.assert_metrics(coffee_node(
            "elixir", "brewing/fulfillment.ex", f"Coffee.Brewing.Fulfillment.{name}",
        ), expected)

    def test_kotlin_each_short_circuit_operator_without_boolean_depth(self) -> None:
        self.assert_metrics(coffee_node(
            "kotlin", "orders/Fulfillment.kt", "Fulfillment.ready",
        ), (5, 0, 0, 5, 1))  # Entry, if, three operators.
        self.assert_metrics(coffee_node("kotlin", "brewing/Brewer.kt", "Brewer.score"),
                            (5, 1, 1, 7, 3))

    def test_python_refutable_match_patterns_and_fallbacks(self) -> None:
        self.assert_python("event", (4, 0, 0, 4, 1))
        for name in ("ignore_event", "retain_event", "record_event", "wrap_event", "normalize_event"):
            with self.subTest(name=name):
                self.assert_python(name, (1, 0, 0, 1, 0))

    def test_python_fallback_guards_are_decisions(self) -> None:
        for name in ("accept_event", "retain_paid_event", "record_paid_event"):
            with self.subTest(name=name):
                self.assert_python(name, (3, 0, 0, 3, 1))

    def test_python_case_guard_depth_does_not_leak_into_body(self) -> None:
        # Active=1; case=2; guard/body-if=3; fallback body-if=2.
        self.assert_python("dispatch", (6, 2, 0, 8, 3))

    def test_python_match_nesting_and_nested_functions(self) -> None:
        self.assert_python("scan", (6, 2, 0, 8, 4))
        self.assert_python("scan.collect", (3, 0, 0, 3, 2))

    def test_elixir_if_unless_and_qualified_non_controls(self) -> None:
        self.assert_elixir("dispatch", (5, 0, 0, 5, 2))

    def test_elixir_case_and_cond_default_arm_exclusion(self) -> None:
        self.assert_elixir("acknowledge", (3, 0, 0, 3, 1))
        self.assert_elixir("priority", (5, 0, 0, 5, 2))

    def test_elixir_guarded_case_alternatives_and_deep_penalties(self) -> None:
        # Case arm=3; guard=4; body if=4; boolean adds no depth.
        self.assert_elixir("release", (7, 3, 0, 10, 4))
        self.assert_elixir("accept_event", (3, 0, 0, 3, 2))

    def test_elixir_declaration_and_lambda_guards(self) -> None:
        self.assert_metrics(coffee_node(
            "elixir", "brewing/recipe.ex", "Coffee.Brewing.Recipe.new",
        ), (3, 0, 0, 3, 1))
        self.assert_metrics(coffee_node(
            "elixir", "brewing/inventory.ex", "Coffee.Brewing.Inventory.available.<anonymous>",
        ), (3, 0, 0, 3, 1))
        self.assert_metrics(coffee_node(
            "elixir", "brewing/brewer.ex", "Coffee.Brewing.Brewer.serve.<anonymous>",
        ), (4, 0, 0, 4, 2))

    def test_elixir_reducer_calls_are_not_loops_and_fn_scopes_are_independent(self) -> None:
        node = coffee_node("elixir", "brewing/brewer.ex", "Coffee.Brewing.Brewer.score")
        self.assert_metrics(node, (1, 0, 0, 1, 0))
        stack = [node]
        callables = []
        while stack:
            child = stack.pop()
            if child.type == "anonymous_function":
                callables.append(child)
            stack.extend(reversed(child.named_children))
        self.assertEqual(len(callables), 2)
        self.assert_metrics(callables[0], (1, 0, 0, 1, 0))
        self.assert_metrics(callables[1], (3, 0, 0, 3, 1))

    def test_elixir_nested_declaration_scopes(self) -> None:
        for name in ("install_public", "install_private", "install_macro"):
            with self.subTest(name=name):
                self.assert_elixir(name, (2, 0, 0, 2, 1))

    def test_elixir_quoted_declarations_have_independent_bodies(self) -> None:
        self.assert_elixir("install_public.pickup", (3, 0, 0, 3, 1))
        self.assert_elixir("install_private.authorize_pickup", (3, 0, 0, 3, 1))
        self.assert_elixir("install_macro.pickup_due", (3, 0, 0, 3, 1))
        self.assert_elixir("install_public.Receipt", (1, 0, 0, 1, 0))
        self.assert_elixir("install_public.Receipt.label", (2, 0, 0, 2, 1))

    def test_else_if_chains_share_depth_across_grammars(self) -> None:
        samples = {
            "typescript": ("ordering/Fulfillment.ts", "Fulfillment.route"),
            "javascript": ("ordering/Fulfillment.js", "Fulfillment.route"),
            "java": ("orders/Fulfillment.java", "Fulfillment.route"),
            "kotlin": ("orders/Fulfillment.kt", "Fulfillment.route"),
            "go": ("brewing/fulfillment.go", "route"),
            "rust": ("brewing/fulfillment.rs", "route"),
            "python": ("src/coffee/orders/fulfillment.py", "Fulfillment.route"),
        }
        for language, (path, name) in samples.items():
            with self.subTest(language=language):
                self.assert_metrics(coffee_node(language, path, name), (5, 0, 0, 5, 2))

    def test_default_arms_remain_excluded_across_grammars(self) -> None:
        samples = {
            "typescript": ("brewing/Recipe.ts", "Recipe.portions"),
            "javascript": ("brewing/Recipe.js", "Recipe.portions"),
            "java": ("brewing/Recipe.java", "Recipe.portions"),
            "kotlin": ("brewing/Recipe.kt", "portions"),
            "go": ("recipe/recipe.go", "Portions"),
            "rust": ("brewing/recipe.rs", "portions"),
            "python": ("src/coffee/brewing/recipe.py", "Recipe.portions"),
            "elixir": ("brewing/recipe.ex", "Coffee.Brewing.Recipe.portions"),
        }
        for language, (path, name) in samples.items():
            with self.subTest(language=language):
                self.assert_metrics(coffee_node(language, path, name), (3, 0, 0, 3, 1))

    def test_braced_else_is_real_nesting_not_else_if(self) -> None:
        for language, path in (("kotlin", "orders/Fulfillment.kt"),
                               ("typescript", "ordering/Fulfillment.ts")):
            with self.subTest(language=language):
                self.assert_metrics(coffee_node(language, path, "Fulfillment.reassign"),
                                    (4, 1, 0, 5, 3))

    def assert_callable_body(self, node: Node) -> None:
        body = node.child_by_field_name("body")
        if body is None:
            body = next(c for c in node.named_children if c.type == "function_body")
        self.assert_metrics(body, (2, 0, 0, 2, 1))

    def test_callable_roots_use_bodies_not_parameter_defaults(self) -> None:
        samples = {
            "python": "src/coffee/orders/fulfillment.py",
            "typescript": "ordering/Fulfillment.ts",
            "kotlin": "orders/Fulfillment.kt",
        }
        for language, path in samples.items():
            with self.subTest(language=language):
                node = coffee_node(language, path, "Fulfillment.quote")
                self.assert_metrics(node, (2, 0, 0, 2, 1))
                self.assert_callable_body(node)


if __name__ == "__main__":
    unittest.main()
