"""Production-indexed CLI navigation queries shared by tests and regeneration."""

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from atlas.cli import main
from atlas.persistence.database import migrate_database
from tests.coffee_fixture import FIXTURE_ROOT, PARSE_ERROR_PATHS, SNAPSHOT_ROOT, coffee_sources
from tests.coffee_scenarios import EMPTY_BREW_CALL

NAVIGATION_SNAPSHOT_ROOT = SNAPSHOT_ROOT / "coffee"

# Source-reviewed paths, qualified declarations and kinds, not saved graph keys.
DECLARATIONS = {
    "java": ("Brewer.java", "Recipe.java", "Report.java", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "kotlin": ("Brewer.kt", "Recipe.kt", "Report.kt", "Brewer.brew", "portions", "render", "function"),
    "go": ("brewer.go", "recipe.go", "report.go", "brew", "Portions", "Render", "function"),
    "rust": ("brewer.rs", "recipe.rs", "report.rs", "brew", "portions", "render", "function"),
    "javascript": ("Brewer.js", "Recipe.js", "Report.js", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "typescript": ("Brewer.ts", "Recipe.ts", "Report.ts", "Brewer.brew", "Recipe.portions", "Report.render", "method"),
    "elixir": ("brewer.ex", "recipe.ex", "report.ex", "Coffee.Brewing.Brewer.brew", "Coffee.Brewing.Recipe.portions", "Coffee.Reporting.Report.render", "function"),
    "python": ("brewer.py", "recipe.py", "report.py", "Brewer.brew", "Recipe.portions", "Report.render", "function"),
}
BASES = {"java": ("Brewing", "interface"), "kotlin": ("CoffeeMaker", "interface"),
         "javascript": ("Brewing", "class"), "typescript": ("Brewing", "interface"),
         "python": ("Brewing", "class")}
FILE_IMPORT_CYCLES = {"rust", "javascript", "typescript", "python"}
Record = dict[str, Any]


@dataclass(frozen=True)
class Declaration:
    path: str
    name: str
    kind: str
    start_line: int | None = None
    level: str = "callable"

    def matches(self, node: Record) -> bool:
        identity = (node["path"], node["qualifiedName"], node["kind"], node["level"])
        expected = (self.path, f"{self.path}::{self.name}", self.kind, self.level)
        return identity == expected and (self.start_line is None or node["startLine"] == self.start_line)


def command(runner: CliRunner, *args: str) -> Record:
    result = runner.invoke(main, list(args))
    assert result.exit_code == 0, f"{args}: {result.output}\n{result.exception}"
    assert not result.stderr, result.stderr
    return json.loads(result.output)


def declaration(nodes: list[Record], expected: Declaration) -> Record:
    matches = [node for node in nodes if expected.matches(node)]
    assert len(matches) == 1, (expected, matches)
    node, = matches
    assert node["name"] == expected.name.rsplit(".", 1)[-1]
    return node


def file_node(nodes: list[Record], path: str) -> Record:
    matches = [node for node in nodes if node["path"] == node["qualifiedName"] == path
               and node["kind"] == node["level"] == "file"]
    assert len(matches) == 1, (path, matches)
    node, = matches
    return node


def navigation_responses(language: str, database: Path) -> Record:
    """Assertions run during regeneration too, before any snapshot is written."""
    migrate_database(database)
    with patch.dict(os.environ, {"DATABASE_PATH": str(database)}):
        root = FIXTURE_ROOT / language
        indexed = command(CliRunner(), "index", "--folder", str(root))
        assert indexed["stats"]["files"] == len(coffee_sources(language))
        assert indexed["stats"]["parseErrors"] == len(PARSE_ERROR_PATHS.get(language, set()))
        return CoffeeNavigation(root, indexed["repositoryId"]).collect()


@dataclass
class CoffeeNavigation:
    root: Path
    project: str
    runner: CliRunner = field(default_factory=CliRunner)
    responses: Record = field(default_factory=dict)
    selected: dict[str, Record] = field(default_factory=dict)

    def query(self, label: str, *args: str) -> Record:
        payload = command(self.runner, "graph", "--project", self.project, *args)
        self.responses[label] = payload
        return payload

    def collect(self) -> Record:
        self.query("overview", "overview")
        self.find_core()
        self.select_core()
        self.show_render()
        self.calls()
        self.source("source_render", self.selected["render"])
        self.imports()
        self.inheritance()
        self.callback()
        self.recursion()
        assert self.responses["overview"]["repositoryId"] == self.project
        return normalize_responses(self.responses, self.root)

    def find_core(self) -> None:
        for query in ("render", "brew", "portions"):
            self.query(f"find_{query}", "find", query, "--limit", "100")

    def select_core(self) -> None:
        brewer, recipe, report, brew_name, portions_name, render_name, kind = DECLARATIONS[self.root.name]
        base = "src/coffee/" if self.root.name == "python" else ""
        brew_line = 10 if self.root.name == "elixir" else None
        recipe_folder = "recipe" if self.root.name == "go" else "brewing"
        selectors = {
            "render": Declaration(f"{base}reporting/{report}", render_name, kind),
            "brew": Declaration(f"{base}brewing/{brewer}", brew_name, kind, brew_line),
            "portions": Declaration(f"{base}{recipe_folder}/{recipe}", portions_name, kind),
        }
        for role, selector in selectors.items():
            self.selected[role] = declaration(self.responses[f"find_{role}"]["nodes"], selector)

    def show_render(self) -> None:
        render = self.selected["render"]
        shown = self.query("show_render", "show", render["stableKey"])
        assert all(shown["node"][key] == value for key, value in render.items())
        report = file_node(shown["ancestors"], render["path"])
        self.selected["report"] = report
        children = self.query("children_report", "children", report["stableKey"])
        assert children["nodes"] and not children["truncated"]
        assert all(node["parentStableKey"] == report["stableKey"] for node in children["nodes"])

    def calls(self) -> None:
        brew, render, portions = (self.selected[role]["stableKey"] for role in ("brew", "render", "portions"))
        outgoing = self.query("context_brew_out", "context", brew, "--direction", "out", "--relations", "CALLS")
        incoming = self.query("context_portions_in", "context", portions, "--direction", "in", "--relations", "CALLS")
        path = self.query("path_brew_render", "path", brew, render, "--direction", "out", "--relations", "CALLS")
        if self.root.name == "go":
            self.assert_go_render_boundary(path, outgoing, brew)
            assert [row["evidence"] for row in core_edges(incoming)] == ["Portions(r.Name)"]
            return
        assert path["status"] == "found" and path["path"] == [brew, render]
        edge, = path["pathEdges"]
        assert (edge["sourceStableKey"], edge["targetStableKey"], edge["type"]) == (brew, render, "CALLS")
        assert edge["evidence"] == ("Report.render()" if self.root.name == "elixir" else EMPTY_BREW_CALL[self.root.name])
        assert edge in outgoing["edges"]
        assert any(row["targetStableKey"] == portions for row in incoming["edges"])
        assert all(row["type"] == "CALLS" for row in [*outgoing["edges"], *incoming["edges"], *path["edges"]])

    def assert_go_render_boundary(self, path: Record, outgoing: Record, brew: str) -> None:
        assert_no_path(path)
        external = "external:go:callable:Render"
        calls = edges_targeting(outgoing, external)
        assert [edge["evidence"] for edge in calls] == ["reporting.Render(nil)", "reporting.Render(valid)"]
        assert all(edge["sourceStableKey"] == brew for edge in calls)
        assert_unresolved_node(outgoing, external)
        boundary = {"stableKey": external, "reason": "unresolved_or_ambiguous", "expandable": False}
        assert boundary in outgoing["boundaries"] and boundary in path["boundaries"]
        found = self.query("path_brew_external_render", "path", brew, external, "--relations", "CALLS")
        assert found["status"] == "found" and found["path"] == [brew, external]
        assert found["pathEdges"] == calls[:1]

    def source(self, label: str, node: Record) -> Record:
        source = self.query(label, "source", node["stableKey"])["source"]
        assert_verified_source(self.root, node, source)
        return source

    def imports(self) -> None:
        recipe_path = self.selected["portions"]["path"]
        found = self.query("find_recipe_file", "find", recipe_path, "--limit", "100")
        assert not found["truncated"]
        recipe = file_node(found["nodes"], recipe_path)
        report = self.selected["report"]
        for label, seed, target in (("recipe", recipe, report), ("report", report, recipe)):
            payload = self.query(f"context_{label}_imports", "context", seed["stableKey"], "--relations", "IMPORTS", "--depth", "4")
            self.assert_imports(payload, seed, target)

    def assert_imports(self, payload: Record, seed: Record, target: Record) -> None:
        nodes = {node["stableKey"]: node for node in payload["nodes"]}
        assert all(edge["type"] == "IMPORTS" for edge in payload["edges"])
        internal = internal_import_targets(payload, seed["stableKey"])
        # Java/Kotlin/Elixir import declarations, not files: no fabricated containment hops.
        expected = expected_import_paths(self.root.name, seed, target)
        assert [node["path"] for node in internal] == expected
        assert not payload["truncated"]
        assert len(nodes) == len(payload["nodes"])
        if self.root.name in FILE_IMPORT_CYCLES:
            assert_file_import_cycle(payload, self.root.name, {seed["stableKey"], target["stableKey"]})

    def inheritance(self) -> None:
        brew = self.selected["brew"]
        if self.root.name not in BASES:
            self.absent_inheritance(brew)
            return
        name, kind = BASES[self.root.name]
        nodes = self.query("find_base", "find", name, "--limit", "100")["nodes"]
        base = declaration(nodes, Declaration(brew["path"], name, kind, level="type"))
        derived_nodes = self.query("find_derived", "find", "Brewer", "--limit", "100")["nodes"]
        derived = declaration(derived_nodes, Declaration(brew["path"], "Brewer", "class", level="type"))
        for label, seed, direction in (("brewer_inherits_out", derived, "out"), ("base_inherits_in", base, "in")):
            payload = self.query(f"context_{label}", "context", seed["stableKey"], "--direction", direction,
                                 "--relations", "INHERITS", "--depth", "4")
            self.assert_inheritance(payload, (derived, base), direction)

    def absent_inheritance(self, brew: Record) -> None:
        payload = self.query("context_inheritance_absent", "context", brew["stableKey"], "--relations", "INHERITS")
        assert [node["stableKey"] for node in payload["nodes"]] == [brew["stableKey"]]
        assert payload["edges"] == payload["boundaries"] == [] and not payload["truncated"]

    def assert_inheritance(self, payload: Record, types: tuple[Record, Record], direction: str) -> None:
        derived, base = types
        assert payload["filters"]["direction"] == direction
        assert all(edge["type"] == "INHERITS" for edge in payload["edges"])
        pairs = [(edge["sourceStableKey"], edge["targetStableKey"]) for edge in payload["edges"]]
        assert (derived["stableKey"], base["stableKey"]) in pairs
        python_out = self.root.name == "python" and direction == "out"
        assert_core_inheritance_count(payload, pairs, python_out)
        assert not payload["truncated"]
        if python_out:
            unresolved, = [node for node in payload["nodes"] if node["level"] == "unresolved"]
            assert unresolved["name"] == "ABC"
            assert (base["stableKey"], unresolved["stableKey"]) in pairs

    def callback(self) -> None:
        brew, portions = self.selected["brew"], self.selected["portions"]
        children = self.query("children_brew", "children", brew["stableKey"])
        assert not children["truncated"]
        # Python's comprehension calls belong to brew, not a separate callback node.
        assert len(children["nodes"]) == (0 if self.root.name == "python" else 1)
        if self.root.name == "python":
            return
        name = "accept" if self.root.name == "go" else "<anonymous>"
        qualified = brew["qualifiedName"].split("::", 1)[1] + "." + name
        callback = declaration(children["nodes"], Declaration(brew["path"], qualified, "function"))
        assert callback["parentStableKey"] == brew["stableKey"]
        shown = self.query("show_brew_callback", "show", callback["stableKey"])
        assert all(shown["node"][key] == value for key, value in callback.items())
        assert shown["ancestors"][0]["stableKey"] == brew["stableKey"]
        context = self.query("context_callback_out", "context", callback["stableKey"], "--relations", "CALLS")
        edge, = context["edges"]
        target = portions["stableKey"]
        path = self.query("path_callback_portions", "path", callback["stableKey"], target, "--relations", "CALLS")
        if self.root.name == "go":
            assert path["status"] == "not_found" and path["path"] == path["pathEdges"] == []
            target = "external:go:callable:Portions"
            assert edge["evidence"] == "menu.Portions(name)"
            assert context["boundaries"] == [{"stableKey": target, "reason": "unresolved_or_ambiguous", "expandable": False}]
            path = self.query("path_callback_external_portions", "path", callback["stableKey"], target, "--relations", "CALLS")
        else:
            assert context["boundaries"] == []
            assert edge in self.responses["context_portions_in"]["edges"]
        assert (edge["sourceStableKey"], edge["targetStableKey"], edge["type"]) == (callback["stableKey"], target, "CALLS")
        assert not context["truncated"]
        assert path["status"] == "found" and path["path"] == [callback["stableKey"], target]
        assert path["pathEdges"] == [edge]
        source = self.source("source_callback", callback)
        assert edge["evidence"] in "\n".join(source["lines"])

    def recursion(self) -> None:
        found = self.query("find_retry", "find", "retry", "--limit", "100")
        assert not found["truncated"]
        retry, expected = self.retry_clauses(found["nodes"])
        context = self.query("context_retry_out", "context", retry["stableKey"], "--relations", "CALLS", "--depth", "6")
        assert_recursion(context, retry["stableKey"], expected)
        source = self.source("source_retry", retry)
        assert all(edge["evidence"] in "\n".join(source["lines"]) for edge in context["edges"])

    def retry_clauses(self, nodes: list[Record]) -> tuple[Record, set[str]]:
        brew = self.selected["brew"]
        qualified = brew["qualifiedName"].split("::", 1)[1].removesuffix("brew") + "retry"
        line = 27 if self.root.name == "elixir" else None
        retry = declaration(nodes, Declaration(brew["path"], qualified, brew["kind"], line))
        expected = {retry["stableKey"]}
        if self.root.name == "elixir":
            base = declaration(nodes, Declaration(brew["path"], qualified, brew["kind"], 26))
            expected.add(base["stableKey"])
        return retry, expected


def core_edges(payload: Record) -> list[Record]:
    return [edge for edge in payload["edges"] if not (edge.get("path") or "").startswith("edge_cases/")]


def assert_core_inheritance_count(payload: Record, pairs: list[tuple[str, str]], python_out: bool) -> None:
    nodes = {node["stableKey"]: node for node in payload["nodes"]}
    core_pairs = [(source, target) for source, target in pairs
                  if not (nodes[source].get("path") or "").startswith("edge_cases/")]
    assert len(core_pairs) == (2 if python_out else 1)


def edges_targeting(payload: Record, target: str) -> list[Record]:
    return [edge for edge in payload["edges"] if edge["targetStableKey"] == target]


def assert_unresolved_node(payload: Record, key: str) -> None:
    node, = [node for node in payload["nodes"] if node["stableKey"] == key]
    assert (node["level"], node["path"]) == ("unresolved", None)


def assert_no_path(payload: Record) -> None:
    assert (payload["status"], payload["path"], payload["pathEdges"]) == ("not_found", [], [])


def expected_import_paths(language: str, seed: Record, target: Record) -> list[str]:
    if language == "go" or (language == "elixir" and seed["path"] == "reporting/report.ex"):
        return []
    if language == "rust":
        return [seed["path"], target["path"]]
    return [target["path"]]


def assert_file_import_cycle(payload: Record, language: str, sources: set[str]) -> None:
    assert {edge["sourceStableKey"] for edge in payload["edges"]} == sources
    if language == "rust":
        assert len(payload["edges"]) == 5
        assert payload["boundaries"] == [{"stableKey": "external:rust:module:crate::brewing::recipe::Recipe", "reason": "unresolved_or_ambiguous", "expandable": False}]
    else:
        assert len(payload["edges"]) == 2 and payload["boundaries"] == []


def internal_import_targets(payload: Record, seed: str) -> list[Record]:
    nodes = {node["stableKey"]: node for node in payload["nodes"]}
    direct = [nodes[edge["targetStableKey"]] for edge in payload["edges"] if edge["sourceStableKey"] == seed]
    return [node for node in direct if node["level"] != "unresolved"]


def assert_recursion(context: Record, retry: str, expected: set[str]) -> None:
    keys = [node["stableKey"] for node in context["nodes"]]
    assert set(keys) == expected and len(keys) == len(expected)
    assert len(context["edges"]) == len(expected)
    pairs = {(edge["sourceStableKey"], edge["targetStableKey"]) for edge in context["edges"]}
    assert pairs == {(retry, key) for key in expected}
    assert all(edge["type"] == "CALLS" for edge in context["edges"])
    assert len({edge["ordinal"] for edge in context["edges"]}) == len(context["edges"])
    assert not context["truncated"] and context["boundaries"] == []


def assert_verified_source(root: Path, node: Record, source: Record) -> None:
    assert source["status"] == "ok" and source["path"] == node["path"]
    assert (source["startLine"], source["endLine"]) == (node["startLine"], node["endLine"])
    assert not source["truncated"] and source["nextStartLine"] is None
    lines = (root / node["path"]).read_bytes().decode("utf-8").split("\n")
    expected = [line.removesuffix("\r") for line in lines[node["startLine"] - 1:node["endLine"]]]
    assert source["lines"] == expected and expected
    if node["name"] != "<anonymous>":
        assert node["name"] in expected[0]


def assert_same_metadata(responses: Record, name: str) -> None:
    values = {response[name] for response in responses.values()}
    assert len(values) == 1 and all(values), (name, values)


def normalize_responses(responses: Record, root: Path) -> Record:
    """Only volatile metadata and absolute sample roots change; never reorder."""
    for name in ("repositoryId", "graphRevision", "indexedAt"):
        assert_same_metadata(responses, name)
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
