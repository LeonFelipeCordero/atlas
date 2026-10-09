"""The metric accumulator consumes adapter policy, never language switches."""

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
            "python": "def run(x):\n match x:\n  case 1: return True\n  case _: return False\n",
            "kotlin": "fun run(x: Int) { if (x > 0) run(x-1) else if(x < 0) run(x+1) }",
            "rust": "fn run(x: i32) { match x { 1 => run(0), _ => () } }",
            "elixir": "defmodule Coffee do\n def run(x) when x > 0 do\n  cond do\n   x > 1 -> 2\n   true -> 1\n  end\n end\nend",
            "java": "class Coffee { void run() { for(;;) { if(ready) break; } } }",
            "go": "package coffee\nfunc run() { for { if ready { break } } }",
            "javascript": "function run(x) { return x && x.ready ? 1 : 0; }",
            "typescript": "function run(x: boolean) { return x ? 1 : 0; }",
            "tsx": "function Run(x: boolean) { return x ? <div /> : <span />; }",
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
        root = get_parser("python").parse(b"if ready: pass\n").root_node
        policy = replace(COMMON_METRICS, decisions=frozenset())
        self.assertEqual(calculate_complexity(root, policy), Complexity(1, 0, 0, 1, 0))
        self.assertEqual(calculate_complexity(root), Complexity(2, 0, 0, 2, 1))


if __name__ == "__main__":
    unittest.main()
