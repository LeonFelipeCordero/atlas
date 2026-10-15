"""Focused assertions for the complete coffee graph scenarios."""

import hashlib
import json
from datetime import datetime

from tests.coffee_fixture import (
    FIXTURE_ROOT,
    SNAPSHOT_ROOT,
    coffee_snapshot,
    coffee_sources,
)
from tests.coffee_scenarios import (
    COMPLEXITY_FIELDS,
    CORE_CALLS,
    EMPTY_BREW_CALL,
    FILTER_CALL,
    SCORE,
    core_calls,
)


def nodes_by_key(graph):
    return {node["stableKey"]: node for node in graph["nodes"]}


def call_edges(graph):
    return [edge for edge in graph["edges"] if edge["type"] == "CALLS"]


def assert_snapshot(test, language, artifact):
    before = artifact.repository.copy()
    actual = coffee_snapshot(artifact)
    expected = json.loads(
        (SNAPSHOT_ROOT / "coffee" / language / "graph.json").read_text(encoding="utf-8")
    )
    # Normalization changes only timestamp and checkout root.
    test.assertEqual(actual, expected)
    test.assertEqual(artifact.repository, before)
    test.assertEqual(before.get("path"), str(FIXTURE_ROOT / language))
    test.assertNotIn("indexedAt", actual["repository"])
    test.assertIsNotNone(datetime.fromisoformat(before.get("indexedAt", "")).tzinfo)
    test.assertEqual(actual["repository"]["path"], f"/samples/coffee/{language}")
    test.assertEqual(actual["repository"]["languages"], sorted({source.language for source in coffee_sources(language)}))
    test.assertEqual(actual["diagnostics"], [])
    test.assertEqual(actual["stats"]["parseErrors"], 0)
    test.assertEqual(actual["stats"]["files"], len(coffee_sources(language)))
    test.assertGreater(actual["stats"]["externalNodes"], 0)
    test.assertTrue(any(edge["type"] == "CALLS" for edge in actual["edges"]))


def assert_layout(test, language, graph):
    root = FIXTURE_ROOT / language
    sources = coffee_sources(language)
    files = {node["path"]: node for node in graph["nodes"] if node["level"] == "file"}
    test.assertEqual(set(files), {source.path for source in sources})
    assert_file_hashes(test, root, files)
    assert_coordinates(test, root, graph)


def assert_file_hashes(test, root, files):
    for path, node in files.items():
        source = (root / path).read_bytes()
        test.assertEqual(node["properties"]["bytes"], len(source))
        test.assertEqual(
            node["properties"]["sha256"], hashlib.sha256(source).hexdigest()
        )


def assert_coordinates(test, root, graph):
    for node in graph["nodes"]:
        if "startLine" not in node:
            continue
        test.assertGreaterEqual(node["endLine"], node["startLine"])
        test.assertLessEqual(
            node["endLine"], len((root / node["path"]).read_bytes().splitlines()) + 1
        )


def assert_recursion_scenarios(test, language, graph):
    assert_callback_owners(test, language, graph)
    required = required_core_calls(language)
    test.assertTrue(required <= core_calls(graph), required - core_calls(graph))


def assert_callback_owners(test, language, graph):
    nodes = nodes_by_key(graph)
    callbacks = [node for node in graph["nodes"] if node["name"] == "<anonymous>"]
    non_callable_owners = [
        (node["qualifiedName"], nodes[node["parentStableKey"]]["qualifiedName"], nodes[node["parentStableKey"]]["level"])
        for node in callbacks if nodes[node["parentStableKey"]]["level"] != "callable"
    ]
    expected_owners = {
        "kotlin": [
            ("orders/OrderService.kt::OrderService.<anonymous>", "orders/OrderService.kt::OrderService", "type"),
            ("reporting/SalesReport.kt::SalesReport.<anonymous>", "reporting/SalesReport.kt::SalesReport", "type"),
            *[("orders/TrackingRates.kt::<anonymous>", "orders/TrackingRates.kt", "file")] * 3,
        ],
        "rust": [("brewing/inventory.rs::<anonymous>", "brewing/inventory.rs", "file")],
        "elixir": [
            (f"brewing/{file}.ex::Coffee.Brewing.{name}.<anonymous>", f"brewing/{file}.ex::Coffee.Brewing.{name}", "module")
            for file, name in (("inventory", "Inventory"), ("order", "Order"), ("recipe", "Recipe"))
        ],
    }
    test.assertCountEqual(non_callable_owners, expected_owners.get(language, []))


def required_core_calls(language):
    required = CORE_CALLS.copy()
    if language == "kotlin":
        required -= {("total", "portions"), ("render", "total")}
    if language in {"java", "elixir"}:
        required.remove(("total", "portions"))
    if language == "elixir":
        required.remove(("render", "portions"))
    if language == "go":
        # Real Go module imports do not resolve locally; focused checks below
        # assert every affected source call rather than pretending it vanished.
        required = {("main", "brew"), ("retry", "retry"), ("render", "total")}
    return required


def assert_call_sites(test, language, graph):
    for edge in graph["edges"]:
        if edge["type"] not in {"CALLS", "REFERENCES", "IMPORTS"}:
            continue
        assert_source_evidence(test, language, edge)


def assert_source_evidence(test, language, edge):
    source = (FIXTURE_ROOT / language / edge["path"]).read_text()
    lines = source.splitlines()
    test.assertIn(
        edge["evidence"].splitlines()[0], lines[edge["line"] - 1], (language, edge)
    )
    test.assertIn(edge["evidence"], source, (language, edge))


def assert_render_paths(test, language, graph):
    nodes = nodes_by_key(graph)
    calls = call_edges(graph)
    brew = [edge for edge in calls if nodes[edge["sourceStableKey"]]["name"] == "brew"]
    render = calls_named(nodes, brew, "render")
    assert_empty_and_nonempty_render(test, language, render)
    test.assertTrue(any(edge["evidence"] == FILTER_CALL[language] for edge in brew))
    target = "receipt" if language == "go" else "render"
    assert_preview_render(test, (nodes, calls), target)


def calls_named(nodes, calls, name):
    return [edge for edge in calls if nodes[edge["targetStableKey"]]["name"].lower() == name]


def assert_empty_and_nonempty_render(test, language, calls):
    evidence = {edge["evidence"] for edge in calls}
    test.assertIn(EMPTY_BREW_CALL[language], evidence)
    test.assertTrue(evidence - {EMPTY_BREW_CALL[language]})


def assert_preview_render(test, context, target):
    nodes, calls = context
    test.assertTrue(
        any(
            nodes[edge["sourceStableKey"]]["name"].lower() == "preview"
            and nodes[edge["targetStableKey"]]["name"].lower() == target
            for edge in calls
        )
    )


def assert_score(test, language, graph):
    scores = [node for node in graph["nodes"] if node["name"] == "score"]
    test.assertEqual(len(scores), 1)
    test.assertEqual(
        tuple(scores[0]["properties"][field] for field in COMPLEXITY_FIELDS),
        SCORE[language],
    )


def assert_project_calls(test, graph):
    language = graph["repository"]["languages"][0]
    nodes = nodes_by_key(graph)
    unresolved = [
        (edge["path"], nodes[edge["targetStableKey"]]["name"], edge["evidence"])
        for edge in call_edges(graph) if is_external_project_call(nodes, edge)
    ]
    # Expanded fixtures expose dynamic-receiver and grouped-alias limitations.
    # Exact exceptions leave every other old/core project call protected.
    expected = {
        "java": [
            ("orders/OrderService.java", "accept", "onReady.accept(order)"),
            ("reporting/Dispatch.java", "accept", "send.accept(Report.render(order.names()))"),
        ],
        "go": [
            ("brewing/brewer.go", "Render", "reporting.Render(nil)"),
            ("brewing/brewer.go", "Portions", "menu.Portions(name)"),
            ("brewing/brewer.go", "Render", "reporting.Render(valid)"),
            ("brewing/brewer.go", "Portions", "menu.Portions(name)"),
            ("brewing/inventory.go", "Portions", "recipe.Portions(name)"),
            ("brewing/fulfillment.go", "Portions", "recipe.Portions(name)"),
            ("reporting/Dispatch.go", "accept", "accept(name)"),
            ("reporting/report.go", "Portions", "recipe.Portions(name)"),
            ("reporting/report.go", "Portions", "recipe.Portions(name)"),
        ],
        "elixir": [
            ("brewing/fulfillment.ex", "total", "order.total"),
            ("reporting/report.ex", "portions", "Recipe.portions(name)"),
            ("reporting/report.ex", "portions", "Recipe.portions(name)"),
            ("reporting/report.ex", "portions", "Recipe.portions"),
        ],
        "kotlin": [("orders/TrackingRates.kt", "total", "order.total()")] * 2,
        "rust": [("main.rs", "portions", "scheduled.portions()")],
        "typescript": [("ordering/Dispatch.ts", "render", "this.render(order)")],
        "javascript": [
            ("ordering/OrderService.js", "brew", "this.brewer.brew(names)"),
            ("ordering/OrderService.js", "render", "this.receipt.render(order)"),
        ],
    }
    test.assertCountEqual(unresolved, expected.get(language, []))


def is_external_project_call(nodes, edge):
    target = nodes[edge["targetStableKey"]]
    return target["level"] == "external" and target["name"].lower() in {
        "brew",
        "render",
        "portions",
        "total",
        "retry",
        "accept",
    }
