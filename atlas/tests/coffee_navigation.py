"""Production-indexed CLI navigation queries shared by tests and regeneration."""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from atlas.cli import main
from atlas.persistence.database import migrate_database
from tests.coffee_fixture import FIXTURE_ROOT, SNAPSHOT_ROOT
from tests.coffee_scenarios import EMPTY_BREW_CALL

NAVIGATION_SNAPSHOT_ROOT = SNAPSHOT_ROOT / "graph-navigation"

# Source-reviewed paths, qualified declarations and kinds, not saved graph keys.
# Elixir's nonempty brew clause is distinguished below by its source line.
DECLARATIONS = {
    "java": ("Brewer.java", "Recipe.java", "Report.java", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "kotlin": ("Brewer.kt", "Recipe.kt", "Report.kt", "Brewer.brew", "portions", "render", "function"),
    "go": ("brewer.go", "recipe.go", "report.go", "brew", "portions", "render", "function"),
    "rust": ("brewer.rs", "recipe.rs", "report.rs", "brew", "portions", "render", "function"),
    "javascript": ("Brewer.js", "Recipe.js", "Report.js", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "typescript": ("Brewer.ts", "Recipe.ts", "Report.ts", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "elixir": ("brewer.ex", "recipe.ex", "report.ex", "Coffee.Brewing.Brewer.brew", "Coffee.Brewing.Recipe.portions", "Coffee.Reporting.Report.render", "function"),
    "python": ("brewer.py", "recipe.py", "report.py", "Brewer.brew", "Recipe.portions", "Report.render", "function"),
}


def command(runner: CliRunner, *args: str) -> dict[str, Any]:
    result = runner.invoke(main, list(args))
    assert result.exit_code == 0, f"{args}: {result.output}\n{result.exception}"
    assert not result.stderr, result.stderr
    return json.loads(result.output)


def declaration(nodes: list[dict[str, Any]], path: str, name: str, kind: str,
                start_line: int | None = None, *, level: str = "callable") -> dict[str, Any]:
    matches = [node for node in nodes if (
        node["path"] == path and node["qualifiedName"] == f"{path}::{name}"
        and node["kind"] == kind and node["level"] == level
        and (start_line is None or node["startLine"] == start_line)
    )]
    assert len(matches) == 1, (path, name, kind, start_line, matches)
    node, = matches
    assert node["name"] == name.rsplit(".", 1)[-1]
    return node


def navigation_responses(language: str, database: Path) -> dict[str, Any]:
    """Assertions run during regeneration too, before any snapshot is written."""
    migrate_database(database)
    with patch.dict(os.environ, {"DATABASE_PATH": str(database)}):
        runner = CliRunner()
        root = FIXTURE_ROOT / language
        indexed = command(runner, "index", "--folder", str(root))
        assert indexed["stats"]["files"] == 3 and indexed["stats"]["parseErrors"] == 0
        prefix = ("graph", "--project", indexed["repositoryId"])
        responses = {"overview": command(runner, *prefix, "overview")}
        for query in ("render", "brew", "portions"):
            options = () if query == "render" else ("--limit", "100")
            responses[f"find_{query}"] = command(runner, *prefix, "find", query, *options)
            assert not responses[f"find_{query}"]["truncated"]
        brewer, recipe, report, brew_name, portions_name, render_name, kind = DECLARATIONS[language]
        base = "src/coffee/" if language == "python" else ""
        render = declaration(responses["find_render"]["nodes"], f"{base}reporting/{report}", render_name, kind)
        brew = declaration(responses["find_brew"]["nodes"], f"{base}brewing/{brewer}", brew_name, kind,
                           start_line=7 if language == "elixir" else None)
        portions = declaration(responses["find_portions"]["nodes"], f"{base}brewing/{recipe}", portions_name, kind)
        responses["show_render"] = command(runner, *prefix, "show", render["stableKey"])
        assert all(responses["show_render"]["node"][key] == value for key, value in render.items())
        files = [node for node in responses["show_render"]["ancestors"]
                 if node["path"] == render["path"] and node["qualifiedName"] == render["path"]
                 and node["kind"] == node["level"] == "file"]
        assert len(files) == 1, files
        report_file, = files
        responses["children_report"] = command(runner, *prefix, "children", report_file["stableKey"])
        assert responses["children_report"]["nodes"] and not responses["children_report"]["truncated"]
        assert all(node["parentStableKey"] == report_file["stableKey"]
                   for node in responses["children_report"]["nodes"])
        responses["context_brew_out"] = command(runner, *prefix, "context", brew["stableKey"],
                                                "--direction", "out", "--relations", "CALLS")
        responses["context_portions_in"] = command(runner, *prefix, "context", portions["stableKey"],
                                                   "--direction", "in", "--relations", "CALLS")
        responses["path_brew_render"] = command(runner, *prefix, "path", brew["stableKey"], render["stableKey"],
                                                "--direction", "out", "--relations", "CALLS")
        assert_static_calls(language, responses, brew["stableKey"], render["stableKey"], portions["stableKey"])
        responses["source_render"] = command(runner, *prefix, "source", render["stableKey"])
        assert_verified_source(root, render, responses["source_render"]["source"])
        add_import_responses(runner, prefix, responses, language, report_file)
        add_inheritance_responses(runner, prefix, responses, language, brew)
        add_callback_responses(runner, prefix, responses, root, brew, portions)
        add_recursion_responses(runner, prefix, responses, root, brew, kind)
        assert responses["overview"]["repositoryId"] == indexed["repositoryId"]
        return normalize_responses(responses, root)


def assert_static_calls(language: str, responses: dict[str, Any], brew: str, render: str, portions: str) -> None:
    path = responses["path_brew_render"]
    assert path["status"] == "found" and path["path"] == [brew, render]
    edge, = path["pathEdges"]
    assert (edge["sourceStableKey"], edge["targetStableKey"], edge["type"]) == (brew, render, "CALLS")
    assert edge["evidence"] == ("Report.render()" if language == "elixir" else EMPTY_BREW_CALL[language])
    outgoing = responses["context_brew_out"]["edges"]
    incoming = responses["context_portions_in"]["edges"]
    assert edge in outgoing
    assert any(row["targetStableKey"] == portions for row in incoming)
    assert all(row["type"] == "CALLS" for row in [*outgoing, *incoming, *path["edges"]])


def assert_verified_source(root: Path, node: dict[str, Any], source: dict[str, Any]) -> None:
    assert source["status"] == "ok" and source["path"] == node["path"]
    assert (source["startLine"], source["endLine"]) == (node["startLine"], node["endLine"])
    assert not source["truncated"] and source["nextStartLine"] is None
    lines = (root / node["path"]).read_bytes().decode("utf-8").split("\n")
    expected = [line.removesuffix("\r") for line in lines[node["startLine"] - 1:node["endLine"]]]
    assert source["lines"] == expected and expected
    if node["name"] != "<anonymous>":
        assert node["name"] in expected[0]


def file_node(nodes: list[dict[str, Any]], path: str) -> dict[str, Any]:
    matches = [node for node in nodes if node["path"] == node["qualifiedName"] == path
               and node["kind"] == node["level"] == "file"]
    assert len(matches) == 1, (path, matches)
    node, = matches
    return node


def add_import_responses(runner: CliRunner, prefix: tuple[str, ...], responses: dict[str, Any],
                         language: str, report: dict[str, Any]) -> None:
    recipe_path = ("src/coffee/" if language == "python" else "") + "brewing/" + DECLARATIONS[language][1]
    recipe = file_node(responses["find_brew"]["nodes"], recipe_path)
    for label, seed, target in (("recipe", recipe, report), ("report", report, recipe)):
        payload = command(runner, *prefix, "context", seed["stableKey"], "--relations", "IMPORTS", "--depth", "4")
        responses[f"context_{label}_imports"] = payload
        nodes = {node["stableKey"]: node for node in payload["nodes"]}
        assert all(edge["type"] == "IMPORTS" for edge in payload["edges"])
        direct = [edge for edge in payload["edges"] if edge["sourceStableKey"] == seed["stableKey"]]
        internal = [nodes[edge["targetStableKey"]] for edge in direct
                    if nodes[edge["targetStableKey"]]["level"] != "external"]
        # Java/Kotlin/Elixir import declarations; other samples import files.
        # Navigation must not fabricate containment hops to make a file cycle.
        assert [node["path"] for node in internal] == ([] if language == "go" else [target["path"]])
        assert not payload["truncated"]
        assert len(nodes) == len(payload["nodes"])
        if language in {"rust", "javascript", "typescript", "python"}:
            assert {edge["sourceStableKey"] for edge in payload["edges"]} == {recipe["stableKey"], report["stableKey"]}
            assert len(payload["edges"]) == 2 and payload["boundaries"] == []


def add_inheritance_responses(runner: CliRunner, prefix: tuple[str, ...], responses: dict[str, Any],
                              language: str, brew: dict[str, Any]) -> None:
    bases = {"java": ("Brewing", "interface"), "kotlin": ("CoffeeMaker", "interface"),
             "javascript": ("Brewing", "class"), "typescript": ("Brewing", "interface"),
             "python": ("Brewing", "class")}
    counts = {row["type"]: row["count"] for row in responses["overview"]["relations"]}
    if language not in bases:
        assert counts.get("INHERITS", 0) == 0
        payload = command(runner, *prefix, "context", brew["stableKey"], "--relations", "INHERITS")
        responses["context_inheritance_absent"] = payload
        assert [node["stableKey"] for node in payload["nodes"]] == [brew["stableKey"]]
        assert payload["edges"] == payload["boundaries"] == [] and not payload["truncated"]
        return
    name, kind = bases[language]
    nodes = responses["find_brew"]["nodes"]
    base = declaration(nodes, brew["path"], name, kind, level="type")
    derived = declaration(nodes, brew["path"], "Brewer", "class", level="type")
    for label, seed, direction in (("brewer_inherits_out", derived, "out"), ("base_inherits_in", base, "in")):
        payload = command(runner, *prefix, "context", seed["stableKey"], "--direction", direction,
                          "--relations", "INHERITS", "--depth", "4")
        responses[f"context_{label}"] = payload
        assert all(edge["type"] == "INHERITS" for edge in payload["edges"])
        pairs = [(edge["sourceStableKey"], edge["targetStableKey"]) for edge in payload["edges"]]
        assert (derived["stableKey"], base["stableKey"]) in pairs
        assert len(pairs) == (2 if language == "python" and direction == "out" else 1)
        assert not payload["truncated"]
        if language == "python" and direction == "out":
            external, = [node for node in payload["nodes"] if node["level"] == "external"]
            assert external["name"] == "ABC"
            assert (base["stableKey"], external["stableKey"]) in pairs


def add_callback_responses(runner: CliRunner, prefix: tuple[str, ...], responses: dict[str, Any],
                           root: Path, brew: dict[str, Any], portions: dict[str, Any]) -> None:
    children = command(runner, *prefix, "children", brew["stableKey"])
    responses["children_brew"] = children
    assert not children["truncated"]
    # Python's comprehension calls belong to brew, not a separate callback node.
    assert len(children["nodes"]) == (0 if root.name == "python" else 1)
    if root.name == "python":
        return
    name = "accept" if root.name == "go" else "<anonymous>"
    qualified = brew["qualifiedName"].split("::", 1)[1] + "." + name
    callback = declaration(children["nodes"], brew["path"], qualified, "function")
    assert callback["parentStableKey"] == brew["stableKey"]
    shown = command(runner, *prefix, "show", callback["stableKey"])
    responses["show_brew_callback"] = shown
    assert all(shown["node"][key] == value for key, value in callback.items())
    assert shown["ancestors"][0]["stableKey"] == brew["stableKey"]
    context = command(runner, *prefix, "context", callback["stableKey"], "--relations", "CALLS")
    responses["context_callback_out"] = context
    edge, = context["edges"]
    assert (edge["sourceStableKey"], edge["targetStableKey"], edge["type"]) == (
        callback["stableKey"], portions["stableKey"], "CALLS")
    assert not context["truncated"] and context["boundaries"] == []
    assert edge in responses["context_portions_in"]["edges"]
    path = command(runner, *prefix, "path", callback["stableKey"], portions["stableKey"], "--relations", "CALLS")
    responses["path_callback_portions"] = path
    assert path["status"] == "found" and path["path"] == [callback["stableKey"], portions["stableKey"]]
    assert path["pathEdges"] == [edge]
    source = command(runner, *prefix, "source", callback["stableKey"])
    responses["source_callback"] = source
    assert_verified_source(root, callback, source["source"])
    assert edge["evidence"] in "\n".join(source["source"]["lines"])


def add_recursion_responses(runner: CliRunner, prefix: tuple[str, ...], responses: dict[str, Any],
                            root: Path, brew: dict[str, Any], kind: str) -> None:
    found = command(runner, *prefix, "find", "retry")
    responses["find_retry"] = found
    assert not found["truncated"]
    qualified = brew["qualifiedName"].split("::", 1)[1].removesuffix("brew") + "retry"
    retry = declaration(found["nodes"], brew["path"], qualified, kind,
                        start_line=12 if root.name == "elixir" else None)
    context = command(runner, *prefix, "context", retry["stableKey"], "--relations", "CALLS", "--depth", "6")
    responses["context_retry_out"] = context
    keys = [node["stableKey"] for node in context["nodes"]]
    expected = {retry["stableKey"]}
    if root.name == "elixir":
        base = declaration(found["nodes"], brew["path"], qualified, kind, start_line=11)
        expected.add(base["stableKey"])
    assert set(keys) == expected and len(keys) == len(expected)
    assert len(context["edges"]) == len(expected)
    pairs = {(edge["sourceStableKey"], edge["targetStableKey"]) for edge in context["edges"]}
    assert pairs == {(retry["stableKey"], key) for key in expected}
    assert all(edge["type"] == "CALLS" for edge in context["edges"])
    assert len({edge["ordinal"] for edge in context["edges"]}) == len(context["edges"])
    assert not context["truncated"] and context["boundaries"] == []
    source = command(runner, *prefix, "source", retry["stableKey"])
    responses["source_retry"] = source
    assert_verified_source(root, retry, source["source"])
    assert all(edge["evidence"] in "\n".join(source["source"]["lines"]) for edge in context["edges"])


def normalize_responses(responses: dict[str, Any], root: Path) -> dict[str, Any]:
    """Only volatile metadata and absolute sample roots change; never reorder."""
    for field in ("repositoryId", "graphRevision", "indexedAt"):
        values = {response[field] for response in responses.values()}
        assert len(values) == 1 and all(values), (field, values)
    normalized = deepcopy(responses)
    for response in normalized.values():
        response.update(repositoryId="<repository-id>", graphRevision="<graph-revision>", indexedAt="<indexed-at>")
    return normalize_root(normalized, str(root), f"/samples/coffee/{root.name}")


def normalize_root(value: Any, root: str, replacement: str) -> Any:
    if isinstance(value, dict):
        return {key: normalize_root(item, root, replacement) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_root(item, root, replacement) for item in value]
    if isinstance(value, str) and (value == root or value.startswith(root + "/")):
        return replacement + value[len(root):]
    return value
