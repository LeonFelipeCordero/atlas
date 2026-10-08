"""Scenario assertions for coffee ownership and resolved project dependencies."""

from tests.coffee_snapshot_assertions import call_edges, nodes_by_key
from tests.coffee_scenarios import COMPLEXITY_FIELDS


def named_node(nodes, name):
    return next(node for node in nodes.values() if node["name"] == name)


def assert_oo_contract(test, language, graph):
    nodes = nodes_by_key(graph)
    brewer = named_node(nodes, "Brewer")
    contract = "CoffeeMaker" if language == "kotlin" else "Brewing"
    inherited = [
        edge
        for edge in graph["edges"]
        if edge["type"] == "INHERITS" and edge["sourceStableKey"] == brewer["stableKey"]
    ]
    test.assertEqual(len(inherited), 1)
    test.assertEqual(nodes[inherited[0]["targetStableKey"]]["name"], contract)
    test.assertEqual(nodes[inherited[0]["targetStableKey"]]["level"], "type")
    assert_brewer_construction(test, graph, nodes, brewer)


def assert_brewer_construction(test, graph, nodes, brewer):
    constructions = [
        edge
        for edge in call_edges(graph)
        if edge["targetStableKey"] == brewer["stableKey"]
    ]
    test.assertEqual(len(constructions), 1)
    test.assertEqual(nodes[constructions[0]["sourceStableKey"]]["name"], "main")


def assert_go_closure(test, graph):
    nodes = nodes_by_key(graph)
    accept = named_node(nodes, "accept")
    brew = named_node(nodes, "brew")
    test.assertEqual(accept["parentStableKey"], brew["stableKey"])
    test.assertEqual(accept["properties"]["cyclomaticComplexity"], 1)
    calls = call_edges(graph)
    test.assertTrue(
        any(
            edge["sourceStableKey"] == brew["stableKey"]
            and edge["targetStableKey"] == accept["stableKey"]
            for edge in calls
        )
    )
    test.assertTrue(
        any(
            edge["sourceStableKey"] == accept["stableKey"]
            and nodes[edge["targetStableKey"]]["name"] == "portions"
            for edge in calls
        )
    )


def assert_elixir_recursion(test, graph):
    nodes = nodes_by_key(graph)
    retry_calls = [
        edge
        for edge in call_edges(graph)
        if nodes[edge["targetStableKey"]]["name"] == "retry"
    ]
    test.assertEqual(len(retry_calls), 2)
    test.assertEqual(
        {edge["evidence"] for edge in retry_calls}, {"retry(attempts - 1)"}
    )
    test.assertEqual(len({edge["sourceStableKey"] for edge in retry_calls}), 1)
    test.assertTrue(
        any(edge["sourceStableKey"] == edge["targetStableKey"] for edge in retry_calls)
    )
    assert_elixir_inner_metrics(test, nodes)


def assert_elixir_inner_metrics(test, nodes):
    test.assertFalse(
        any(
            node["level"] == "external" and node["name"] in {"if", "case"}
            for node in nodes.values()
        )
    )
    inner = next(
        node
        for node in nodes.values()
        if "score.<anonymous>.<anonymous>" in node.get("qualifiedName", "")
    )
    test.assertEqual(
        tuple(inner["properties"][key] for key in COMPLEXITY_FIELDS), (3, 0, 0, 3, 1)
    )


def workflow_cases(language):
    cases = [
        ("brew", "render", "reporting/"),
        ("brew", "portions", "brewing/recipe."),
        ("score", "portions", "brewing/recipe."),
        ("preview", "render", "reporting/"),
        ("render", "portions", "brewing/recipe."),
    ]
    if language != "kotlin":
        cases += [("render", "total", "reporting/")]
    if language not in {"kotlin", "java"}:
        cases += [("total", "portions", "brewing/recipe.")]
    return cases


def workflow_owner(nodes, edge):
    source = nodes[edge["sourceStableKey"]]
    while source["name"] in {"<anonymous>", "accept"}:
        source = nodes[source["parentStableKey"]]
    return source


def matches_workflow(nodes, edge, source_name, target_name, target_path):
    source = workflow_owner(nodes, edge)
    target = nodes[edge["targetStableKey"]]
    if source["name"].lower() != source_name:
        return False
    return (
        target["name"] == target_name and target_path in (target["path"] or "").lower()
    )


def assert_workflow_case(test, language, graph, nodes, case):
    source_name, target_name, target_path = case
    with test.subTest(source=source_name, target=target_name):
        matches = [
            edge
            for edge in call_edges(graph)
            if matches_workflow(nodes, edge, source_name, target_name, target_path)
        ]
        test.assertTrue(matches, (language, source_name, target_name))


def assert_workflow(test, language, graph):
    nodes = nodes_by_key(graph)
    for case in workflow_cases(language):
        assert_workflow_case(test, language, graph, nodes, case)
    if language == "java":
        assert_java_workflow_references(test, graph, nodes)


def assert_java_workflow_references(test, graph, nodes):
    test.assertEqual(
        [
            (
                nodes[edge["sourceStableKey"]]["name"],
                nodes[edge["targetStableKey"]]["path"],
            )
            for edge in graph["edges"]
            if edge["type"] == "REFERENCES"
        ],
        [("total", "brewing/Recipe.java")],
    )


def assert_library_output(test, graph, name):
    nodes = nodes_by_key(graph)
    test.assertTrue(
        any(
            edge["type"] == "CALLS" and nodes[edge["targetStableKey"]]["name"] == name
            for edge in graph["edges"]
        )
    )
