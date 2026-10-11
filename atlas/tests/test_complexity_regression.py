"""Source-derived complexity expectations, independent of graph snapshots."""

from tests.source_snapshot_fixture import case_text
from tests.parsing_snapshot_support import source_variants

import unittest

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity


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
            case_text('metrics', 'complexity_regression-kotlin_each_short_circuit_operator_without_boolean_depth-kotlin', 'sample.kt'),
            (5, 0, 0, 5, 1),  # Entry, if, three operators.
        )
        self.measure(
            "kotlin",
            case_text('metrics', 'complexity_regression-kotlin_each_short_circuit_operator_without_boolean_depth-kotlin-2', 'sample.kt'),
            (5, 1, 1, 7, 3),
        )

    def test_python_refutable_match_patterns_and_fallbacks(self) -> None:
        self.measure(
            "python",
            case_text('metrics', 'complexity-python-match-refutable-alternatives', 'sample.py'),
            (4, 0, 0, 4, 1),
        )
        fallbacks = ("_", "captured", "_ as captured", "(captured)", "0 | _")
        cases = source_variants('test_complexity_regression', 'test_python_refutable_match_patterns_and_fallbacks', 'python')[1:]
        for pattern, case in zip(fallbacks, cases, strict=True):
            with self.subTest(pattern=pattern):
                self.measure(
                    "python",
                    case_text(case['family'], case['case_id'], case['path']),
                    (1, 0, 0, 1, 0),
                )

    def test_python_fallback_guards_are_decisions(self) -> None:
        cases = source_variants('test_complexity_regression', 'test_python_fallback_guards_are_decisions', 'python')
        for pattern, case in zip(("_", "captured", "_ as captured"), cases, strict=True):
            with self.subTest(pattern=pattern):
                self.measure(
                    "python",
                    case_text(case['family'], case['case_id'], case['path']),
                    (3, 0, 0, 3, 1),  # Guard and its conjunction, not the fallback.
                )

    def test_python_case_guard_depth_does_not_leak_into_body(self) -> None:
        self.measure(
            "python",
            case_text('metrics', 'complexity_regression-python_case_guard_depth_does_not_leak_into_body-python', 'sample.py'),
            (6, 2, 0, 8, 3),
            # Active=1; case=2; guard/body-if=3; fallback body-if=2.
        )

    def test_python_match_nesting_and_nested_functions(self) -> None:
        self.measure(
            "python",
            case_text('metrics', 'complexity_regression-python_match_nesting_and_nested_functions-python', 'sample.py'),
            (6, 2, 0, 8, 4),
        )

    def test_elixir_if_unless_and_qualified_non_controls(self) -> None:
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_if_unless_and_qualified_non_controls-elixir', 'sample.ex'),
            (5, 0, 0, 5, 2),
        )

    def test_elixir_case_and_cond_default_arm_exclusion(self) -> None:
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_case_and_cond_default_arm_exclusion-elixir', 'sample.ex'),
            (3, 0, 0, 3, 1),  # Unlike cond, true is a refutable case pattern.
        )
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_case_and_cond_default_arm_exclusion-elixir-2', 'sample.ex'),
            (5, 0, 0, 5, 2),
        )

    def test_elixir_guarded_case_alternatives_and_deep_penalties(self) -> None:
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_guarded_case_alternatives_and_deep_penalties-elixir', 'sample.ex'),
            (7, 3, 0, 10, 4),
            # Case arm=3; guard=4; body if=4; boolean adds no depth.
        )
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_guarded_case_alternatives_and_deep_penalties-elixir-2', 'sample.ex'),
            (3, 0, 0, 3, 2),  # Guarded wildcard is not a default arm.
        )

    def test_elixir_declaration_and_lambda_guards(self) -> None:
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_declaration_and_lambda_guards-elixir', 'sample.ex'),
            (4, 0, 0, 4, 1),
        )
        self.measure(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_declaration_and_lambda_guards-elixir-2', 'sample.ex'),
            (5, 0, 0, 5, 1),  # Fn clauses are not case alternatives.
        )

    def test_elixir_reducer_calls_are_not_loops_and_fn_scopes_are_independent(
        self,
    ) -> None:
        node = self.parse(
            "elixir",
            case_text('metrics', 'complexity_regression-elixir_reducer_calls_are_not_loops_and_fn_scopes_are_independent-elixir', 'sample.ex'),
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
        cases = source_variants('test_complexity_regression', 'test_elixir_nested_declaration_scopes', 'elixir')
        for declaration, case in zip(('def', 'defp', 'defmacro'), cases, strict=True):
            with self.subTest(declaration=declaration):
                self.measure(
                    "elixir",
                    case_text(case['family'], case['case_id'], case['path']),
                    (2, 0, 0, 2, 1),
                )

    def test_else_if_chains_share_depth_across_grammars(self) -> None:
        samples = {
            "typescript": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-typescript', 'sample.ts'),
            "javascript": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-typescript', 'sample.ts'),
            "java": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-java', 'sample.java'),
            "kotlin": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-kotlin', 'sample.kt'),
            "go": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-go', 'sample.go'),
            "rust": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-rust', 'sample.rs'),
            "python": case_text('metrics', 'complexity_regression-else_if_chains_share_depth_across_grammars-python', 'sample.py'),
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.measure(language, source, (5, 0, 0, 5, 2))

    def test_default_arms_remain_excluded_across_grammars(self) -> None:
        samples = {
            "typescript": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-typescript', 'sample.ts'),
            "javascript": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-typescript', 'sample.ts'),
            "java": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-java', 'sample.java'),
            "kotlin": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-kotlin', 'sample.kt'),
            "go": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-go', 'sample.go'),
            "rust": case_text('metrics', 'complexity_regression-default_arms_remain_excluded_across_grammars-rust', 'sample.rs'),
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.measure(language, source, (2, 0, 0, 2, 1))

    def test_braced_else_is_real_nesting_not_else_if(self) -> None:
        for language, source in (
            ("kotlin", case_text('metrics', 'complexity_regression-braced_else_is_real_nesting_not_else_if-kotlin', 'sample.kt')),
            ("typescript", case_text('metrics', 'complexity_regression-braced_else_is_real_nesting_not_else_if-typescript', 'sample.ts')),
        ):
            with self.subTest(language=language):
                self.measure(language, source, (4, 1, 0, 5, 3))

    def test_callable_roots_use_bodies_not_parameter_defaults(self) -> None:
        samples = {
            "python": case_text('metrics', 'complexity_regression-callable_roots_use_bodies_not_parameter_defaults-python', 'sample.py'),
            "typescript": case_text('metrics', 'complexity_regression-callable_roots_use_bodies_not_parameter_defaults-typescript', 'sample.ts'),
            "kotlin": case_text('metrics', 'complexity_regression-callable_roots_use_bodies_not_parameter_defaults-kotlin', 'sample.kt'),
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
