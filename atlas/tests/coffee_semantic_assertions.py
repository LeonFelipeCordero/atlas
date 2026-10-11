"""Scenario assertions for coffee ownership and resolved project dependencies."""

from dataclasses import dataclass

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
    assert_brewer_construction(test, graph, brewer)


def assert_brewer_construction(test, graph, brewer):
    nodes = nodes_by_key(graph)
    constructions = [
        edge
        for edge in call_edges(graph)
        if edge["targetStableKey"] == brewer["stableKey"]
    ]
    language = graph["repository"]["languages"][0]
    expected = {
        "java": ["main", "OrderService"], "kotlin": ["main", "OrderService"],
        "javascript": ["main", "constructor"], "typescript": ["main", "constructor"],
        "python": ["main", "stocked"],
    }
    test.assertCountEqual([nodes[edge["sourceStableKey"]]["name"] for edge in constructions], expected[language])


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
            and nodes[edge["targetStableKey"]]["name"] == "Portions"
            and nodes[edge["targetStableKey"]]["level"] == "external"
            and edge["evidence"] == "menu.Portions(name)"
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
    test.assertEqual(len(retry_calls), 4)
    recursive = calls_from_owner(nodes, retry_calls, "retry")
    assert_recursive_dispatch(test, recursive)
    from_main = calls_from_owner(nodes, retry_calls, "main")
    test.assertEqual(len(from_main), 2)
    test.assertEqual({edge["evidence"] for edge in from_main}, {"retry(2)"})
    assert_elixir_inner_metrics(test, nodes)


def calls_from_owner(nodes, calls, name):
    return [edge for edge in calls if nodes[edge["sourceStableKey"]]["name"] == name]


def assert_recursive_dispatch(test, calls):
    test.assertEqual(len(calls), 2)
    test.assertEqual({edge["evidence"] for edge in calls}, {"retry(attempts - 1)"})
    test.assertEqual(len({edge["sourceStableKey"] for edge in calls}), 1)
    test.assertTrue(any(edge["sourceStableKey"] == edge["targetStableKey"] for edge in calls))


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
    if language == "go":
        return [("render", "Total", "reporting/"), ("dose", "Portions", "recipe/"), ("preview", "Receipt", "reporting/")]
    cases = [
        ("brew", "render", "reporting/"),
        ("brew", "portions", "brewing/recipe."),
        ("score", "portions", "brewing/recipe."),
        ("preview", "render", "reporting/"),
        ("render", "portions", "brewing/recipe."),
    ]
    if language != "kotlin":
        cases += [("render", "total", "reporting/")]
    if language not in {"kotlin", "java", "elixir"}:
        cases += [("total", "portions", "brewing/recipe.")]
    if language == "elixir":
        cases.remove(("render", "portions", "brewing/recipe."))
    return cases


def workflow_owner(nodes, edge):
    source = nodes[edge["sourceStableKey"]]
    while source["name"] in {"<anonymous>", "accept"}:
        source = nodes[source["parentStableKey"]]
    return source


@dataclass(frozen=True)
class WorkflowContext:
    language: str
    nodes: dict
    calls: list


def matches_workflow(nodes, edge, case):
    source_name, target_name, target_path = case
    source = workflow_owner(nodes, edge)
    target = nodes[edge["targetStableKey"]]
    if source["name"].lower() != source_name:
        return False
    return (
        target["name"] == target_name and target_path in (target["path"] or "").lower()
    )


def assert_workflow_case(test, context, case):
    source_name, target_name, target_path = case
    with test.subTest(source=source_name, target=target_name):
        matches = [
            edge
            for edge in context.calls
            if matches_workflow(context.nodes, edge, case)
        ]
        test.assertTrue(matches, (context.language, source_name, target_name))


def assert_workflow(test, language, graph):
    nodes = nodes_by_key(graph)
    context = WorkflowContext(language, nodes, call_edges(graph))
    for case in workflow_cases(language):
        assert_workflow_case(test, context, case)
    if language == "java":
        assert_java_workflow_references(test, graph, nodes)
    if language == "go":
        assert_go_module_limitations(test, graph)
    if language == "elixir":
        assert_elixir_grouped_alias_limitation(test, graph)


def assert_java_workflow_references(test, graph, nodes):
    test.assertEqual(
        [
            (
                nodes[edge["sourceStableKey"]]["name"],
                nodes[edge["targetStableKey"]]["path"],
            )
            for edge in graph["edges"]
            if edge["type"] == "REFERENCES" and edge["path"] == "reporting/Report.java"
        ],
        [("total", "brewing/Recipe.java")],
    )


def module_imports(graph, fragment):
    return [edge for edge in graph["edges"] if edge["type"] == "IMPORTS" and fragment in edge["evidence"]]


def external_calls_named(graph, names):
    nodes = nodes_by_key(graph)
    return [edge for edge in call_edges(graph) if nodes[edge["targetStableKey"]]["level"] == "external" and nodes[edge["targetStableKey"]]["name"] in names]


def source_edges(graph, kind, path):
    return [edge for edge in graph["edges"] if edge["type"] == kind and edge["path"] == path]


def assert_go_module_limitations(test, graph):
    """Go cannot map example.com module imports to local packages yet."""
    nodes = nodes_by_key(graph)
    imports = module_imports(graph, "example.com/coffee/")
    test.assertCountEqual([(edge["path"], edge["evidence"]) for edge in imports], [
        ("brewing/brewer.go", 'menu "example.com/coffee/recipe"'),
        ("brewing/brewer.go", '"example.com/coffee/reporting"'),
        ("brewing/inventory.go", '"example.com/coffee/recipe"'),
        ("brewing/order.go", '"example.com/coffee/recipe"'),
        ("main.go", '"example.com/coffee/brewing"'),
        ("reporting/report.go", '"example.com/coffee/recipe"'),
    ])
    test.assertTrue(all(nodes[edge["targetStableKey"]]["level"] == "external" for edge in imports))
    names = {"Normalize", "Render", "Portions", "Preview", "New", "Scale", "Dose", "Main"}
    calls = external_calls_named(graph, names)
    test.assertCountEqual([(edge["path"], edge["evidence"]) for edge in calls], [
        ("brewing/brewer.go", "menu.Normalize(name)"),
        ("brewing/brewer.go", "reporting.Render(nil)"),
        ("brewing/brewer.go", "menu.Portions(name)"),
        ("brewing/brewer.go", "reporting.Render(valid)"),
        ("brewing/brewer.go", "menu.Portions(name)"),
        ("brewing/brewer.go", 'reporting.Preview("espresso")'),
        ("brewing/inventory.go", "recipe.Portions(name)"),
        ("brewing/order.go", 'recipe.New("filter", len(order.Names))'),
        ("brewing/order.go", "drink.Scale(len(order.Names), 0)"),
        ("brewing/order.go", "scaled.Dose()"),
        ("main.go", "brewing.Main()"),
        ("reporting/report.go", "recipe.Portions(name)"),
        ("reporting/report.go", "recipe.Portions(name)"),
    ])


def assert_elixir_grouped_alias_limitation(test, graph):
    """Grouped aliases are not expanded; individual aliases still resolve."""
    nodes = nodes_by_key(graph)
    imports = source_edges(graph, "IMPORTS", "reporting/report.ex")
    test.assertEqual([edge["evidence"] for edge in imports], ["alias Coffee.Brewing.{Inventory, Recipe}"])
    test.assertEqual(nodes[imports[0]["targetStableKey"]]["level"], "external")
    calls = source_edges(graph, "CALLS", "reporting/report.ex")
    affected = [edge for edge in calls if nodes[edge["targetStableKey"]]["name"] in {"portions", "available"}]
    test.assertCountEqual([edge["evidence"] for edge in affected], ["Recipe.portions(name)", "Recipe.portions(name)", "Inventory.available(stock, names)", "Recipe.portions"])
    test.assertTrue(all(nodes[edge["targetStableKey"]]["level"] == "external" for edge in affected))


def assert_library_output(test, graph, name):
    nodes = nodes_by_key(graph)
    test.assertTrue(
        any(
            edge["type"] == "CALLS" and nodes[edge["targetStableKey"]]["name"] == name
            for edge in graph["edges"]
        )
    )
