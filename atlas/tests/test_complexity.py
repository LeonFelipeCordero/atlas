from tests.source_snapshot_fixture import case_text

import tempfile
import unittest
from pathlib import Path

from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity
from atlas.indexer import analyze_repository


class ComplexityTests(unittest.TestCase):
    def measure(self, source: str, language: str = "typescript") -> Complexity:
        return calculate_complexity(
            get_parser(language).parse(source.encode()).root_node.named_children[0]
        )

    def test_entry_and_sequential_decisions(self) -> None:
        self.assertEqual(self.measure(case_text('metrics', 'complexity-entry_and_sequential_decisions-typescript', 'sample.ts')), Complexity(1, 0, 0, 1, 0))
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-entry_and_sequential_decisions-typescript-2', 'sample.ts')), Complexity(4, 0, 0, 4, 1)
        )

    def test_requested_example_across_grammars(self) -> None:
        samples = {
            "typescript": case_text('metrics', 'complexity-requested_example_across_grammars-typescript', 'sample.ts'),
            "javascript": case_text('metrics', 'complexity-requested_example_across_grammars-typescript', 'sample.ts'),
            "python": case_text('metrics', 'complexity-requested_example_across_grammars-python', 'sample.py'),
            "java": case_text('metrics', 'complexity-requested_example_across_grammars-java', 'sample.java'),
            "kotlin": case_text('metrics', 'complexity-requested_example_across_grammars-kotlin', 'sample.kt'),
            "go": case_text('metrics', 'complexity-requested_example_across_grammars-go', 'sample.go'),
            "rust": case_text('metrics', 'complexity-requested_example_across_grammars-rust', 'sample.rs'),
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.assertEqual(
                    self.measure(source, language), Complexity(5, 2, 1, 8, 4)
                )

    def test_depths_three_and_five(self) -> None:
        for depth, case_id in ((3, 'complexity-depth-3-typescript'),
                               (5, 'complexity-depth-5-typescript')):
            with self.subTest(depth=depth):
                source = case_text('metrics', case_id, 'sample.ts')
                self.assertEqual(
                    self.measure(source),
                    Complexity(depth + 1, depth - 2, 0, 2 * depth - 1, depth),
                )

    def test_penalty_per_deep_decision_not_only_maximum(self) -> None:
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-penalty_per_deep_decision_not_only_maximum-typescript', 'sample.ts')), Complexity(5, 2, 0, 7, 3)
        )

    def test_loop_ancestor_need_not_be_immediate_parent(self) -> None:
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-loop_ancestor_need_not_be_immediate_parent-typescript', 'sample.ts')),
            Complexity(5, 2, 2, 9, 4),
        )
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-loop_ancestor_need_not_be_immediate_parent-typescript-2', 'sample.ts')), Complexity(3, 0, 0, 3, 1)
        )

    def test_boolean_ternary_and_catch(self) -> None:
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-boolean_ternary_and_catch-typescript', 'sample.ts')), Complexity(4, 0, 0, 4, 1)
        )
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-boolean_ternary_and_catch-typescript-2', 'sample.ts')),
            Complexity(3, 0, 0, 3, 1),
        )

    def test_else_if_is_not_nesting(self) -> None:
        self.assertEqual(
            self.measure(case_text('metrics', 'complexity-else_if_is_not_nesting-typescript', 'sample.ts')),
            Complexity(5, 0, 0, 5, 1),
        )
        source = case_text('metrics', 'complexity-else_if_is_not_nesting-python', 'sample.py')
        self.assertEqual(self.measure(source, "python"), Complexity(4, 0, 0, 4, 1))

    def test_nested_scopes_are_not_counted(self) -> None:
        source = case_text('metrics', 'complexity-nested_scopes_are_not_counted-typescript', 'sample.ts')
        self.assertEqual(self.measure(source), Complexity(2, 0, 0, 2, 1))

    def test_python_method_and_inner_function_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text(
                case_text('metrics', 'complexity-python_method_and_inner_function_are_independent-python', 'example.py')
            )
            artifact = analyze_repository(root)
            by_name = {node["name"]: node for node in artifact.nodes}
            self.assertEqual(by_name["run"]["properties"]["cyclomaticComplexity"], 2)
            self.assertEqual(by_name["inner"]["properties"]["cyclomaticComplexity"], 3)
            self.assertEqual(by_name["inner"]["properties"]["loopNestedComplexity"], 0)
            self.assertNotIn("cyclomaticComplexity", by_name["A"]["properties"])

    def test_artifact_only_function_and_method_properties(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.ts").write_text(case_text('metrics', 'complexity-artifact_only_function_and_method_properties-typescript', 'example.ts'))
            nodes = analyze_repository(root).nodes
            by_name = {
                node["name"]: node
                for node in nodes
                if node["type"] in {"function", "method"}
            }
            self.assertEqual(by_name["run"]["properties"]["cyclomaticComplexity"], 8)
            self.assertEqual(
                by_name["run"]["properties"]["nestedCyclomaticComplexity"], 2
            )
            self.assertEqual(by_name["run"]["properties"]["loopNestedComplexity"], 1)
            self.assertEqual(by_name["outer"]["properties"]["cyclomaticComplexity"], 2)
            self.assertEqual(by_name["inner"]["properties"]["cyclomaticComplexity"], 6)
            self.assertEqual(by_name["empty"]["properties"]["cyclomaticComplexity"], 1)
            for node in nodes:
                if node["type"] not in {"function", "method"}:
                    self.assertNotIn("cyclomaticComplexity", node["properties"])
                    self.assertNotIn("nestedCyclomaticComplexity", node["properties"])
                    self.assertNotIn("loopNestedComplexity", node["properties"])


if __name__ == "__main__":
    unittest.main()
