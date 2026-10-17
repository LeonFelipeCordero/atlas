"""Exact distinct-peer and reverse-reachability metrics on small graphs."""

from copy import deepcopy
from typing import cast

import pytest

from atlas.domain.models import GraphView
from atlas.metrics.dependency_metrics import dependency_metrics
from tests.metrics.metric_core_support import edge


@pytest.mark.parametrize(("nodes", "pairs", "expected"), [
    ([], [], {}),
    (["alone"], [], {"alone": (0, 0, 0, None)}),
    (["a", "b", "c"], [("a", "b"), ("b", "c")],
     {"a": (0, 1, 0, 1.0), "b": (1, 1, 1, 0.5), "c": (1, 0, 2, 0.0)}),
    (["a", "b", "c", "d"], [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
     {"a": (0, 2, 0, 1.0), "b": (1, 1, 1, 0.5), "c": (1, 1, 1, 0.5), "d": (2, 0, 3, 0.0)}),
    (["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "b"), ("c", "d")],
     {"a": (0, 1, 0, 1.0), "b": (2, 1, 2, 1 / 3),
      "c": (1, 2, 2, 2 / 3), "d": (1, 0, 3, 0.0)}),
])
def test_dependency_metrics(nodes, pairs, expected) -> None:
    view = cast(GraphView, {"nodes": nodes, "edges": [edge(a, b) for a, b in pairs]})

    result = dependency_metrics(view)

    assert result == {key: dict(zip(
        ("fanIn", "fanOut", "transitiveChangeImpact", "instability"), values
    )) for key, values in expected.items()}


def test_duplicate_self_and_external_edges_do_not_change_peer_counts() -> None:
    view = cast(GraphView, {"nodes": ["a", "b", "isolated"], "edges": [
        edge("a", "b", count=99), edge("a", "b"), edge("a", "a"),
        edge("a", "external"), edge("external", "b"),
    ]})
    before = deepcopy(view)

    result = dependency_metrics(view)

    assert result == {
        "a": {"fanIn": 0, "fanOut": 1, "transitiveChangeImpact": 0, "instability": 1.0},
        "b": {"fanIn": 1, "fanOut": 0, "transitiveChangeImpact": 1, "instability": 0.0},
        "isolated": {"fanIn": 0, "fanOut": 0, "transitiveChangeImpact": 0, "instability": None},
    }
    assert view == before


def test_reverse_impact_is_independent_of_input_order() -> None:
    view = cast(GraphView, {"nodes": ["d", "c", "b", "a"], "edges": [
        edge("c", "d"), edge("b", "c"), edge("a", "b"),
    ]})

    result = dependency_metrics(view)

    assert {key: values["transitiveChangeImpact"] for key, values in result.items()} == {
        "a": 0, "b": 1, "c": 2, "d": 3,
    }
