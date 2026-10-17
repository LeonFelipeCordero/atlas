"""Deterministic file import groups, ownership, exclusions, and SCC order."""

from copy import deepcopy
import hashlib
import json

import pytest

from atlas.metrics.cycles import circular_dependencies, strongly_connected_components
from tests.metrics.metric_core_support import edge, graph_node


@pytest.fixture
def nodes() -> list[dict[str, object]]:
    return [graph_node(key, "file") for key in ("a", "b", "c", "d")]


def group(keys: list[str], cycle: list[str], edges: list[dict[str, object]]) -> dict[str, object]:
    digest = hashlib.sha256(json.dumps(keys, ensure_ascii=True).encode()).hexdigest()
    return {"id": f"import-cycle:{digest}", "nodeStableKeys": keys,
            "exampleCycle": cycle, "edges": edges}


def test_scc_components_are_source_first_with_sorted_members() -> None:
    adjacency = {"d": [], "c": ["b", "d"], "b": ["c"], "a": ["b"]}

    result = strongly_connected_components(adjacency)

    assert result == [["a"], ["b", "c"], ["d"]]


@pytest.mark.parametrize("adjacency", [{}, {"a": []}, {"a": ["a"]}])
def test_scc_empty_isolated_and_self_connected(adjacency) -> None:
    assert strongly_connected_components(adjacency) == ([] if not adjacency else [["a"]])


def test_scc_long_chain_does_not_need_recursion() -> None:
    adjacency = {str(i): [str(i + 1)] if i < 1499 else [] for i in range(1500)}

    result = strongly_connected_components(adjacency)

    assert result == [[str(i)] for i in range(1500)]


def test_projection_retains_metadata_and_duplicates_and_ignores_cross_group_edges(nodes) -> None:
    nodes.extend([graph_node("a.fn", "callable", parent="a"), graph_node("b.type", "type", parent="b")])
    forward = edge("a.fn", "b.type", path="a.py", line=3, evidence="import b", ignored="drop")
    reverse = edge("b", "a", path="b.py", line=2)
    edges = [edge("c", "d"), reverse, forward, forward, edge("b", "c")]
    before = deepcopy((nodes, edges))
    projected_forward = edge("a", "b", path="a.py", line=3, evidence="import b")
    projected_reverse = edge("b", "a", path="b.py", line=2)

    result = circular_dependencies(nodes, edges)

    assert result == {"version": 1, "groups": [group(
        ["a", "b"], ["a", "b", "a"],
        sorted([projected_forward, projected_forward, projected_reverse],
               key=lambda item: json.dumps(item, sort_keys=True)),
    )]}
    assert (nodes, edges) == before
    assert circular_dependencies(list(reversed(nodes)), list(reversed(edges))) == result


@pytest.mark.parametrize(("forward", "extra_nodes"), [
    (edge("a", "b", kind="CALLS"), []),
    (edge("a", "b", typeOnly=True), []),
    (edge("a", "external"), [graph_node("external", "external")]),
    (edge("missing", "b"), []),
    (edge("orphan", "b"), [graph_node("orphan", "symbol", parent="missing")]),
    (edge("x", "b"), [graph_node("x", "symbol", parent="y"), graph_node("y", "symbol", parent="x")]),
])
def test_excluded_imports_cannot_close_a_cycle(nodes, forward, extra_nodes) -> None:
    result = circular_dependencies(nodes + extra_nodes, [forward, edge("b", "a")])

    assert result == {"version": 1, "groups": []}


@pytest.mark.parametrize("endpoints", [("fn", "fn"), ("a", "fn"), ("fn", "a")])
def test_symbol_imports_within_the_same_file_are_not_self_cycles(nodes, endpoints) -> None:
    nodes.append(graph_node("fn", "callable", parent="a"))

    result = circular_dependencies(nodes, [edge(*endpoints)])

    assert result == {"version": 1, "groups": []}


def test_direct_file_self_import_counts_and_groups_sort_by_members(nodes) -> None:
    aa, dd = edge("a", "a"), edge("d", "d")

    result = circular_dependencies(nodes, [dd, aa])

    assert result == {"version": 1, "groups": [group(["a"], ["a", "a"], [aa]),
                                              group(["d"], ["d", "d"], [dd])]}


def test_non_true_type_only_flag_is_not_excluded(nodes) -> None:
    edges = [edge("a", "b", typeOnly=False), edge("b", "a")]

    result = circular_dependencies(nodes, edges)

    assert result == {"version": 1, "groups": [group(["a", "b"], ["a", "b", "a"],
                                                   [edge("a", "b"), edge("b", "a")])]}


def test_example_cycle_uses_sorted_first_neighbor_then_shortest_return_path(nodes) -> None:
    nodes.append(graph_node("e", "file"))
    edges = [edge("a", "c"), edge("a", "b"), edge("b", "d"),
             edge("b", "c"), edge("c", "a"), edge("d", "e"), edge("e", "a")]

    result = circular_dependencies(nodes, edges)

    assert result == {"version": 1, "groups": [group(
        ["a", "b", "c", "d", "e"], ["a", "b", "c", "a"],
        sorted(edges, key=lambda item: json.dumps(item, sort_keys=True)),
    )]}


def test_edges_between_separate_cycle_groups_are_not_reported_as_internal(nodes) -> None:
    ab, ba, cc = edge("a", "b"), edge("b", "a"), edge("c", "c")

    result = circular_dependencies(nodes, [ab, ba, cc, edge("b", "c")])

    assert result == {"version": 1, "groups": [
        group(["a", "b"], ["a", "b", "a"], [ab, ba]), group(["c"], ["c", "c"], [cc]),
    ]}


def test_empty_graph_has_versioned_empty_report() -> None:
    assert circular_dependencies([], []) == {"version": 1, "groups": []}
