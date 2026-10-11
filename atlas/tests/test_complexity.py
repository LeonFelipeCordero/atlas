from tests.source_snapshot_fixture import case_text

import unittest

from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity
from atlas.indexer import analyze_repository
from tests.coffee_consolidation import COFFEE_ROOT, coffee_node


class ComplexityTests(unittest.TestCase):
    def measure(self, source: str, language: str = "typescript") -> Complexity:
        return calculate_complexity(
            get_parser(language).parse(source.encode()).root_node.named_children[0]
        )

    def test_entry_and_sequential_decisions(self) -> None:
        self.assertEqual(calculate_complexity(coffee_node(
            "typescript", "brewing/Brewer.ts", "Brewer.calibrate",
        )), Complexity(1, 0, 0, 1, 0))
        # Eight sequential category decisions add eight entries, no depth penalty.
        self.assertEqual(calculate_complexity(coffee_node(
            "python", "src/coffee/brewing/brewer.py", "Brewer.classify",
        )), Complexity(9, 0, 0, 9, 1))

    def test_requested_example_across_grammars(self) -> None:
        samples = {
            "typescript": ("brewing/Brewer.ts", "Brewer.score"),
            "javascript": ("brewing/Brewer.js", "Brewer.score"),
            "python": ("src/coffee/brewing/brewer.py", "Brewer.score"),
            "java": ("brewing/Brewer.java", "Brewer.score"),
            "kotlin": ("brewing/Brewer.kt", "Brewer.score"),
            "go": ("brewing/brewer.go", "score"),
            "rust": ("brewing/brewer.rs", "score"),
        }
        for language, (path, name) in samples.items():
            with self.subTest(language=language):
                # Entry + two loops + if + conjunction. The if is depth three;
                # only the inner loop has a loop ancestor.
                self.assertEqual(calculate_complexity(coffee_node(language, path, name)),
                                 Complexity(5, 1, 1, 7, 3))

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
        artifact = analyze_repository(COFFEE_ROOT / "python")
        by_name = {node["qualifiedName"]: node for node in artifact.nodes}
        prefix = "src/coffee/reporting/sales.py::SalesReport"
        self.assertEqual(by_name[prefix + ".totals"]["properties"]["cyclomaticComplexity"], 4)
        self.assertEqual(by_name[prefix + ".totals.collect"]["properties"]["cyclomaticComplexity"], 3)
        self.assertEqual(by_name[prefix + ".totals.collect"]["properties"]["loopNestedComplexity"], 0)
        self.assertNotIn("cyclomaticComplexity", by_name[prefix]["properties"])

    def test_artifact_only_function_and_method_properties(self) -> None:
        nodes = analyze_repository(COFFEE_ROOT / "typescript").nodes
        by_name = {node["qualifiedName"]: node for node in nodes}
        score = by_name["brewing/Brewer.ts::Brewer.score"]["properties"]
        self.assertEqual(score["cyclomaticComplexity"], 7)
        self.assertEqual(score["nestedCyclomaticComplexity"], 1)
        self.assertEqual(score["loopNestedComplexity"], 1)
        prefix = "ordering/Orders.ts::"
        self.assertEqual(by_name[prefix + "drinkTickets"]["properties"]["cyclomaticComplexity"], 4)
        self.assertEqual(by_name[prefix + "drinkTickets.ticket"]["properties"]["cyclomaticComplexity"], 1)
        self.assertEqual(by_name["brewing/Brewer.ts::Brewer.calibrate"]["properties"]["cyclomaticComplexity"], 1)
        for node in nodes:
            if node["type"] not in {"function", "method"}:
                self.assertNotIn("cyclomaticComplexity", node["properties"])
                self.assertNotIn("nestedCyclomaticComplexity", node["properties"])
                self.assertNotIn("loopNestedComplexity", node["properties"])


if __name__ == "__main__":
    unittest.main()
