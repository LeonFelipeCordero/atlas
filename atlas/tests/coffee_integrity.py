"""Reference and aggregation checks beyond GraphArtifact's schema validation."""

from dataclasses import dataclass
from typing import Any
from unittest import TestCase


@dataclass(frozen=True)
class GraphRelations:
    nodes: dict[str, Any]
    contains: set[tuple[str, str]]


def assert_node_ancestry(test, node, relations):
    nodes, contains = relations.nodes, relations.contains
    ancestors = node["ancestorStableKeys"]
    test.assertEqual(node["depth"], len(ancestors))
    test.assertTrue(set(ancestors) <= nodes.keys())
    if not node["parentStableKey"]:
        return
    parent = nodes[node["parentStableKey"]]
    test.assertEqual(ancestors, parent["ancestorStableKeys"] + [parent["stableKey"]])
    if node["level"] != "external":
        test.assertIn((parent["stableKey"], node["stableKey"]), contains)


def assert_view_edge(test, edge, view):
    test.assertIn(edge["sourceStableKey"], view["nodes"])
    test.assertIn(edge["targetStableKey"], view["nodes"])
    test.assertEqual(edge["count"], sum(edge["relationshipCounts"].values()))
    test.assertEqual(edge["count"], sum(edge["confidenceCounts"].values()))


def assert_view(test, view, expected_nodes):
    test.assertEqual(view["nodes"], expected_nodes)
    for edge in view["edges"]:
        assert_view_edge(test, edge, view)


def assert_cycle_edge(test, edge, members):
    test.assertEqual(edge["type"], "IMPORTS")
    test.assertIn(edge["sourceStableKey"], members)
    test.assertIn(edge["targetStableKey"], members)


def assert_cycle_group(test, group, nodes):
    members = set(group["nodeStableKeys"])
    test.assertTrue(members <= nodes.keys())
    test.assertTrue(all(nodes[key]["level"] == "file" for key in members))
    test.assertEqual(group["exampleCycle"][0], group["exampleCycle"][-1])
    test.assertTrue(set(group["exampleCycle"]) <= members)
    for edge in group["edges"]:
        assert_cycle_edge(test, edge, members)


def assert_level_stats(test, graph, nodes):
    for level, stat in (
        ("file", "files"), ("module", "modules"), ("type", "types"),
        ("callable", "callables"), ("external", "externalNodes"),
    ):
        test.assertEqual(graph["stats"][stat], len(level_node_keys(nodes, level)))


def level_node_keys(nodes, level):
    return [key for key, node in nodes.items() if node["level"] == level]


def assert_coffee_integrity(test: TestCase, graph: dict[str, Any]) -> None:
    nodes = {node["stableKey"]: node for node in graph["nodes"]}
    contains = {
        (edge["sourceStableKey"], edge["targetStableKey"])
        for edge in graph["edges"] if edge["type"] == "CONTAINS"
    }
    relations = GraphRelations(nodes, contains)
    for node in nodes.values():
        assert_node_ancestry(test, node, relations)
    for level, view in graph["views"].items():
        assert_view(test, view, level_node_keys(nodes, level))
    for group in graph["circularDependencies"]["groups"]:
        assert_cycle_group(test, group, nodes)
    test.assertEqual(graph["stats"]["nodes"], len(nodes))
    test.assertEqual(graph["stats"]["edges"], len(graph["edges"]))
    assert_level_stats(test, graph, nodes)
