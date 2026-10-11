"""The metric accumulator consumes adapter policy, never language switches."""

from tests.source_snapshot_fixture import case_bytes, case_text

import unittest
from dataclasses import replace

from tree_sitter_language_pack import get_parser

from atlas.metrics.adapters import get_metric_adapter
from atlas.metrics.adapters.base import COMMON_METRICS
from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity


class MetricAdapterTest(unittest.TestCase):
    def test_primary_policies_preserve_node_only_api(self):
        samples = {
            "python": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-python', 'sample.py'),
            "kotlin": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-kotlin', 'sample.kt'),
            "rust": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-rust', 'sample.rs'),
            "elixir": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-elixir', 'sample.ex'),
            "java": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-java', 'sample.java'),
            "go": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-go', 'sample.go'),
            "javascript": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-javascript', 'sample.js'),
            "typescript": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-typescript', 'sample.ts'),
            "tsx": case_text('metrics', 'metric_adapters-primary_policies_preserve_node_only_api-tsx', 'sample.tsx'),
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.assert_node_only_policy(language, source)

    def assert_node_only_policy(self, language, source):
        root = get_parser(language).parse(source.encode()).root_node
        self.assertFalse(root.has_error)
        adapter = get_metric_adapter(language)
        stack = [root]
        while stack:
            node = stack.pop()
            if adapter.metrics.scope(node):
                self.assertEqual(
                    calculate_complexity(node, adapter.metrics),
                    calculate_complexity(node),
                )
            stack.extend(node.named_children)

    def test_policy_controls_decisions_without_changing_traversal(self):
        root = get_parser("python").parse(case_bytes('metrics', 'metric_adapters-policy_controls_decisions_without_changing_traversal-python', 'sample.py')).root_node
        policy = replace(COMMON_METRICS, decisions=frozenset())
        self.assertEqual(calculate_complexity(root, policy), Complexity(1, 0, 0, 1, 0))
        self.assertEqual(calculate_complexity(root), Complexity(2, 0, 0, 2, 1))


if __name__ == "__main__":
    unittest.main()
