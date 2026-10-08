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
    CALL_SITES,
    COMPLEXITY_FIELDS,
    CORE_CALLS,
    EMPTY_BREW_CALL,
    FILTER_CALL,
    OBSERVED,
    SCORE,
    core_calls,
    scenario_summary,
)


def nodes_by_key(graph):
    return {node["stableKey"]: node for node in graph["nodes"]}


def call_edges(graph):
    return [edge for edge in graph["edges"] if edge["type"] == "CALLS"]


def assert_snapshot(test, language, artifact):
    before = artifact.repository.copy()
    actual = coffee_snapshot(artifact)
    expected = json.loads(
        (SNAPSHOT_ROOT / f"{language}-coffee.json").read_text(encoding="utf-8")
    )
    # Baselines are never rewritten; only timestamp and root vary.
    test.assertEqual(actual, expected)
    test.assertEqual(artifact.repository, before)
    test.assertEqual(before.get("path"), str(FIXTURE_ROOT / language))
    test.assertNotIn("indexedAt", actual["repository"])
    test.assertIsNotNone(datetime.fromisoformat(before.get("indexedAt", "")).tzinfo)
    test.assertEqual(actual["repository"]["path"], f"/samples/coffee/{language}")
    test.assertEqual(actual["repository"]["languages"], [language])
    test.assertEqual(actual["diagnostics"], [])
    test.assertEqual(actual["stats"]["parseErrors"], 0)
    test.assertEqual(actual["stats"]["files"], 3)
    test.assertGreater(actual["stats"]["externalNodes"], 0)
    test.assertTrue(any(edge["type"] == "CALLS" for edge in actual["edges"]))


def assert_layout(test, language, graph):
    root = FIXTURE_ROOT / language
    sources = coffee_sources(language)
    test.assertEqual(len(sources), 3)
    test.assertEqual(
        sorted(source.path.removeprefix("src/coffee/").split("/")[0] for source in sources),
        ["brewing", "brewing", "reporting"],
    )
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
    test.assertEqual(scenario_summary(graph), OBSERVED[language])
    nodes = nodes_by_key(graph)
    callbacks = [node for node in graph["nodes"] if node["name"] == "<anonymous>"]
    test.assertTrue(
        all(nodes[node["parentStableKey"]]["level"] == "callable" for node in callbacks)
    )
    required = CORE_CALLS.copy()
    if language == "kotlin":
        required -= {("total", "portions"), ("render", "total")}
    if language == "java":
        required.remove(("total", "portions"))
    test.assertTrue(required <= core_calls(graph), required - core_calls(graph))


def assert_call_sites(test, language, graph):
    calls = call_edges(graph)
    sites = {(edge["path"], edge["line"], edge["evidence"]) for edge in calls}
    test.assertEqual(len(sites), CALL_SITES[language])
    test.assertEqual(len(calls) - len(sites), 2 if language == "elixir" else 0)
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
    render = [
        edge for edge in brew if nodes[edge["targetStableKey"]]["name"] == "render"
    ]
    test.assertTrue(
        any(edge["evidence"] == EMPTY_BREW_CALL[language] for edge in render)
    )
    test.assertTrue(any(edge["evidence"] == FILTER_CALL[language] for edge in brew))
    test.assertTrue(
        any(edge["evidence"] != EMPTY_BREW_CALL[language] for edge in render)
    )
    assert_preview_render(test, nodes, calls)


def assert_preview_render(test, nodes, calls):
    test.assertTrue(
        any(
            nodes[edge["sourceStableKey"]]["name"] == "preview"
            and nodes[edge["targetStableKey"]]["name"] == "render"
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
    nodes = nodes_by_key(graph)
    unresolved = [
        edge for edge in call_edges(graph) if is_external_project_call(nodes, edge)
    ]
    test.assertEqual(unresolved, [])


def is_external_project_call(nodes, edge):
    target = nodes[edge["targetStableKey"]]
    return target["level"] == "external" and target["name"] in {
        "brew",
        "render",
        "portions",
        "total",
        "retry",
        "accept",
    }
