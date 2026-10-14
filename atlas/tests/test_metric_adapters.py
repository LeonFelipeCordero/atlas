"""Metric policies preserve node-only traversal on the complete coffee projects."""

from dataclasses import replace

import pytest
from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.adapters import get_metric_adapter
from atlas.metrics.adapters.base import COMMON_METRICS
from atlas.metrics.complexity import calculate_complexity
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_node
from tests.coffee_fixture import LANGUAGES, coffee_sources


def assert_source_policy(source):
    root = get_parser(source.language).parse(source.source).root_node
    assert not root.has_error, source.path
    policy = get_metric_adapter(source.language).metrics
    scopes = [node for node in walk(root) if policy.scope(node)]
    for node in scopes:
        assert calculate_complexity(node, policy) == calculate_complexity(node)
    return len(scopes)


@pytest.mark.parametrize("language", LANGUAGES)
def test_primary_policies_preserve_node_only_api(language):
    assert sum(map(assert_source_policy, coffee_sources(language))) > 0


def test_policy_controls_decisions_without_changing_traversal():
    node = coffee_node("python", "src/coffee/orders/models.py", "Order.transition")
    policy = replace(COMMON_METRICS, decisions=frozenset())
    assert calculate_complexity(node, policy) == Complexity(1, 0, 0, 1, 0)
    assert calculate_complexity(node) == Complexity(3, 0, 0, 3, 1)
