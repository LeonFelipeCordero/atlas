import json
import subprocess
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from shutil import copyfile, copytree, ignore_patterns

from atlas.indexer import analyze_repository
from atlas.parsing.discovery import discover_files
from tests.coffee_fixture import FIXTURE_ROOT

# Analyze whole applications, including Dispatch/Scheduling/Fulfillment. Tracking
# is deliberately excluded while those shared sources are being rewritten.
APPLICATIONS = {
    "typescript": ("brewing/Brewer.ts", "reporting/Report.ts"),
    "javascript": ("brewing/Brewer.js", "reporting/Report.js"),
    "java": ("brewing/Brewer.java", "reporting/Report.java"),
    "kotlin": ("brewing/Brewer.kt", "reporting/Report.kt"),
    "go": ("brewing/brewer.go", "reporting/report.go"),
    "rust": ("brewing/brewer.rs", "reporting/report.rs"),
    "elixir": ("brewing/brewer.ex", "reporting/report.ex"),
    "python": ("src/coffee/brewing/brewer.py", "src/coffee/reporting/report.py"),
}
FILE_COUNTS = dict(zip(APPLICATIONS, (12, 12, 12, 9, 10, 13, 8, 10), strict=True))


def copy_application(language: str, root: Path) -> Path:
    return copytree(FIXTURE_ROOT / language, root,
                    ignore=ignore_patterns("*Tracking*", "*tracking*"))


def go_brewer_symbols() -> list[tuple[str, str, str]]:
    return [("Brewer", "type", "type"), ("Brew", "method", "callable")] + [
        (name, "function", "callable") for name in (
            "NewBrewer", "brew", "brew.accept", "retry", "score", "classify",
            "ready", "calibrate", "Main", "Main.<anonymous>",
        )
    ]


def rust_brewer_symbols() -> list[tuple[str, str, str]]:
    return [("Brewer", "struct", "type"), ("Brewer", "impl", "symbol")] + [
        (name, "function", "callable") for name in (
            "Brewer.new", "Brewer.brew", "Brewer.remaining", "brew",
            "brew.<anonymous>", "retry", "score", "classify", "ready", "calibrate",
        )
    ]


def elixir_brewer_symbols() -> list[tuple[str, str, str]]:
    owner = "Coffee.Brewing.Brewer"
    return [(owner, "module", "module")] + [
        (f"{owner}.{name}", "function", "callable") for name in (
            "brew", "brew", "brew.<anonymous>", "serve", "serve.<anonymous>",
            "retry", "retry", "score", "score.<anonymous>",
            "score.<anonymous>.<anonymous>", "classify", "ready", "calibrate", "main",
        )
    ]


BREWER_CLASSES = {
    "typescript": ("Brewing", "interface", "method"),
    "javascript": ("Brewing", "class", "method"),
    "java": ("Brewing", "interface", "method"),
    "kotlin": ("CoffeeMaker", "interface", "function"),
    "python": ("Brewing", "class", "function"),
}


def class_brewer_symbols(language: str) -> list[tuple[str, str, str]]:
    contract, contract_kind, kind = BREWER_CLASSES[language]
    symbols = [
        (contract, contract_kind, "type"),
        (f"{contract}.brew", kind, "callable"), ("Brewer", "class", "type"),
    ] + [(f"Brewer.{name}", kind, "callable") for name in (
        "brew", "retry", "score", "classify", "ready", "calibrate",
    )]
    symbols.append(("Brewer.main", "method", "callable") if language == "java"
                   else ("main", "function", "callable"))
    if language != "python":
        symbols.append(("Brewer.brew.<anonymous>", "function", "callable"))
    if language in {"typescript", "javascript"}:
        symbols.append(("Brewer.classify.<anonymous>", "function", "callable"))
    if language in {"java", "kotlin"}:
        symbols.append(("coffee.brewing", "module", "module"))
    if language == "python":
        symbols.append(("import_styles", "function", "callable"))
    return symbols


def brewer_symbols(language: str) -> list[tuple[str, str, str]]:
    """Exact declarations in the stable brewing entry point, including closures."""
    special = {"go": go_brewer_symbols, "rust": rust_brewer_symbols,
               "elixir": elixir_brewer_symbols}
    return special[language]() if language in special else class_brewer_symbols(language)


BREWER_IMPORTS = {
    "typescript": ["external:typescript:node:process", "reporting/Report.ts", "brewing/Recipe.ts"],
    "javascript": ["external:javascript:node:process", "brewing/Recipe.js", "reporting/Report.js"],
    "java": ["reporting/Report.java::Report", "external:java:java.util.List"],
    "kotlin": ["reporting/Report.kt::render", "external:kotlin:java.lang.StringBuilder"],
    "go": ["external:go:fmt", "external:go:example.com/coffee/recipe",
           "external:go:example.com/coffee/reporting"],
    "rust": ["brewing/brewer.rs::brew", "external:rust:super::inventory::Inventory",
             "brewing/recipe.rs", "reporting/report.rs"],
    "elixir": ["brewing/inventory.ex::Coffee.Brewing.Inventory",
               "brewing/order.ex::Coffee.Brewing.Order", "brewing/recipe.ex::Coffee.Brewing.Recipe",
               "reporting/report.ex::Coffee.Reporting.Report", "external:elixir:Logger"],
    "python": ["external:python:abc", "external:python:sys"]
              + ["src/coffee/brewing/recipe.py"] * 5 + ["src/coffee/reporting/report.py"] * 5,
}


def reporting_calls(language: str) -> list[tuple[str, str]]:
    if language == "go":
        # The example.com import identity remains external, not a guessed module.
        return []
    if language == "elixir":
        return [("Coffee.Brewing.Brewer.brew", "Coffee.Reporting.Report.render")] * 2 + [
            ("Coffee.Brewing.Brewer.main", "Coffee.Reporting.Report.daily")
        ]
    source = "brew" if language == "rust" else "Brewer.brew"
    target = "render" if language in {"kotlin", "rust"} else "Report.render"
    calls = [(source, target)] * 2
    return calls + [("import_styles", "render")] * 4 if language == "python" else calls


def tree_contents(root: Path) -> dict[Path, bytes | None]:
    return {path.relative_to(root): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


def qualified_edges(artifact, edges):
    nodes = {node["stableKey"]: node for node in artifact.nodes}
    return [(nodes[edge["sourceStableKey"]]["qualifiedName"],
             nodes[edge["targetStableKey"]]["qualifiedName"], edge["relationshipCounts"])
            for edge in edges]


class IndexerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(workspace.cleanup)
        cls.artifacts = {
            language: analyze_repository(copy_application(language, Path(workspace.name) / language))
            for language in APPLICATIONS
        }

    def test_indexes_polyglot_symbols_and_connections(self) -> None:
        for language, (source, report) in APPLICATIONS.items():
            with self.subTest(language=language):
                self.assert_application_symbols((language, source, report))

    def test_rust_dispatch_wiring_preserves_namespace_and_encoder_ownership(self) -> None:
        artifact = self.artifacts["rust"]
        namespaces = [node for node in artifact.nodes
                      if node.get("path") == "main.rs" and node["kind"] == "module"]
        self.assertEqual([node["qualifiedName"] for node in namespaces], [
            "main.rs::brewing", "main.rs::reporting", "main.rs::dispatch",
        ])
        self.assertEqual([node["parentStableKey"] for node in namespaces], ["file:main.rs"] * 3)
        encoder, = [node for node in artifact.nodes
                    if node["qualifiedName"] == "reporting/dispatch_format.rs::encode"]
        self.assertEqual((encoder["kind"], encoder["level"], encoder["parentStableKey"]),
                         ("function", "callable", "file:reporting/dispatch_format.rs"))
        self.assertEqual(encoder["ancestorStableKeys"], [
            "repository", "module:.", "module:reporting", "file:reporting/dispatch_format.rs",
        ])

    def assert_application_symbols(self, case) -> None:
        language, source, report = case
        artifact = self.artifacts[language]
        saved = asdict(artifact)
        self.assertEqual(saved["schemaVersion"], 2)
        self.assertEqual(artifact.stats["files"], FILE_COUNTS[language])
        self.assertEqual(artifact.stats["parseErrors"], 0)
        symbols = [node for node in artifact.nodes
                   if node.get("path") == source and node["level"] != "file"]
        self.assertCountEqual(
            [(node["qualifiedName"].split("::", 1)[1], node["kind"], node["level"])
             for node in symbols], brewer_symbols(language),
        )
        self.assert_brewer_imports(artifact, language, source)
        self.assert_reporting_calls(artifact, case)
        self.assert_graph_structure(artifact)

    def assert_brewer_imports(self, artifact, language, source) -> None:
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        imports = [nodes[edge["targetStableKey"]]["qualifiedName"] for edge in artifact.edges
                   if edge["type"] == "IMPORTS" and edge["sourceStableKey"] == f"file:{source}"]
        self.assertCountEqual(imports, BREWER_IMPORTS[language])

    def assert_reporting_calls(self, artifact, case) -> None:
        language, source, report = case
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        calls = [(nodes[edge["sourceStableKey"]]["qualifiedName"],
                  nodes[edge["targetStableKey"]]["qualifiedName"])
                 for edge in artifact.edges if edge["type"] == "CALLS"
                 and nodes[edge["sourceStableKey"]].get("path") == source
                 and nodes[edge["targetStableKey"]].get("path") == report]
        self.assertCountEqual(calls, [(f"{source}::{caller}", f"{report}::{callee}")
                                      for caller, callee in reporting_calls(language)])

    def assert_graph_structure(self, artifact) -> None:
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        self.assertEqual(len(nodes), len(artifact.nodes))
        for edge in artifact.edges:
            self.assertIn(edge["sourceStableKey"], nodes)
            self.assertIn(edge["targetStableKey"], nodes)
        for node in artifact.nodes:
            if node["level"] in {"repository", "external"}:
                continue
            parent = nodes[node["parentStableKey"]]
            self.assertEqual(node["ancestorStableKeys"],
                             parent["ancestorStableKeys"] + [parent["stableKey"]])
            self.assertEqual(node["depth"], parent["depth"] + 1)
            if node["level"] == "callable":
                self.assertIn(f"file:{node['path']}", node["ancestorStableKeys"])

    def test_builds_polyglot_module_file_type_and_callable_views(self) -> None:
        for language, (source, report) in APPLICATIONS.items():
            with self.subTest(language=language):
                artifact = self.artifacts[language]
                self.assert_view_inventory(artifact)
                self.assert_reporting_views(artifact, (language, source, report))

    def assert_view_inventory(self, artifact) -> None:
        for level in ("module", "file", "type", "callable"):
            self.assert_level_inventory(artifact, level)

    def assert_level_inventory(self, artifact, level) -> None:
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        view = artifact.views[level]
        self.assertEqual(set(view["nodes"]),
                         {key for key, node in nodes.items() if node["level"] == level})
        self.assertEqual(artifact.stats[f"{level}s"], len(view["nodes"]))

    def assert_reporting_views(self, artifact, case) -> None:
        self.assert_reporting_file_view(artifact, case)
        self.assert_reporting_callable_view(artifact, case)
        self.assert_reporting_type_view(artifact, case)
        self.assert_reporting_module_view(artifact, case[0])

    def assert_reporting_file_view(self, artifact, case) -> None:
        language, source, report = case
        file_edges = [edge for edge in artifact.views["file"]["edges"]
                      if edge["sourceStableKey"] == f"file:{source}"
                      and edge["targetStableKey"] == f"file:{report}"]
        counts = {"CALLS": len(reporting_calls(language)),
                  "IMPORTS": 5 if language == "python" else 1}
        self.assertEqual(qualified_edges(artifact, file_edges),
                         [] if language == "go" else [(source, report, counts)])

    def assert_reporting_callable_view(self, artifact, case) -> None:
        language, source, report = case
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        callable_edges = [edge for edge in artifact.views["callable"]["edges"]
                          if nodes[edge["sourceStableKey"]].get("path") == source
                          and nodes[edge["targetStableKey"]].get("path") == report]
        expected = reporting_calls(language)
        if language != "elixir":
            expected = list(dict.fromkeys(expected))
        self.assertCountEqual(qualified_edges(artifact, callable_edges), [
            (f"{source}::{caller}", f"{report}::{callee}",
             {"CALLS": 1 if language == "elixir" else reporting_calls(language).count((caller, callee))})
            for caller, callee in expected
        ])

    def assert_reporting_type_view(self, artifact, case) -> None:
        language, source, report = case
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        edges = [edge for edge in artifact.views["type"]["edges"]
                 if nodes[edge["sourceStableKey"]].get("path") == source
                 and nodes[edge["targetStableKey"]].get("path") == report]
        expected = [] if language in {"go", "rust", "elixir", "kotlin"} else [
            (f"{source}::Brewer", f"{report}::Report", {"CALLS": 2})
        ]
        self.assertEqual(qualified_edges(artifact, edges), expected)

    def assert_reporting_module_view(self, artifact, language) -> None:
        source, target, counts = {
            "python": ("src.coffee.brewing", "src.coffee.reporting", {"CALLS": 7, "IMPORTS": 6}),
            "elixir": ("brewing", "reporting/report.ex::Coffee.Reporting.Report", {"IMPORTS": 3}),
        }.get(language, ("brewing", "reporting", {"CALLS": 3, "IMPORTS": 2}))
        edges = [(caller, callee, counts) for caller, callee, counts
                 in qualified_edges(artifact, artifact.views["module"]["edges"])
                 if caller == source and callee == target]
        self.assertEqual(edges, [] if language == "go" else [(source, target, counts)])

    def test_kotlin_class_methods_and_nested_declarations(self) -> None:
        artifact = self.artifacts["kotlin"]
        path = "orders/OrderService.kt"
        nodes = {node["qualifiedName"]: node for node in artifact.nodes if "qualifiedName" in node}
        service = nodes[f"{path}::OrderService"]
        methods = [node for node in artifact.nodes if node["parentStableKey"] == service["stableKey"]
                   and node["level"] == "callable"]
        self.assertCountEqual([node["name"] for node in methods],
                              ["<anonymous>", "place", "place", "fulfill", "preview", "receipts", "notify", "place"])
        self.assertEqual(len({node["stableKey"] for node in methods}), 8)
        self.assertEqual(nodes[f"{path}::CoffeeOrders"]["kind"], "interface")
        self.assert_kotlin_nested_declarations(nodes, path)
        self.assertEqual(nodes["orders/Order.kt::OrderLine.Factory.espresso"]["parentStableKey"],
                         nodes["orders/Order.kt::OrderLine.Factory"]["stableKey"])
        self.assertEqual(nodes["orders/Order.kt::receipt"]["level"], "callable")
        self.assert_service_dependencies(artifact, path, "kt")

    def assert_kotlin_nested_declarations(self, nodes, path) -> None:
        for name, parent, kind, level in (
            ("OrderService.Companion", "OrderService", "class", "type"),
            ("OrderService.Companion.stocked", "OrderService.Companion", "function", "callable"),
            ("OrderService.receipts.formatReady", "OrderService.receipts", "function", "callable"),
            ("OrderService.receipts.<anonymous>", "OrderService.receipts", "function", "callable"),
        ):
            node = nodes[f"{path}::{name}"]
            self.assertEqual((node["kind"], node["level"], node["parentStableKey"]),
                             (kind, level, nodes[f"{path}::{parent}"]["stableKey"]))

    def test_java_tags_add_constructors_without_losing_imports(self) -> None:
        artifact = self.artifacts["java"]
        path = "orders/OrderService.java"
        symbols = [node for node in artifact.nodes if node.get("path") == path
                   and node["level"] != "file"]
        self.assert_java_constructors(artifact, (path, symbols))
        self.assertEqual(sum(node["name"] == "place" for node in symbols), 3)
        self.assert_java_service_imports(artifact, path)
        self.assertEqual(artifact.stats["parseErrors"], 0)
        self.assert_service_dependencies(artifact, path, "java")

    def assert_java_constructors(self, artifact, case) -> None:
        path, symbols = case
        constructors = [node for node in symbols if node["kind"] == "constructor"]
        self.assertCountEqual([node["qualifiedName"] for node in constructors], [
            f"{path}::OrderService.OrderService", f"{path}::OrderService.OrderService",
            f"{path}::OrderService.Factory.Factory",
        ])
        self.assertEqual(len({node["stableKey"] for node in constructors}), 3)
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        for node in constructors:
            self.assertEqual(node["level"], "callable")
            self.assertEqual(nodes[node["parentStableKey"]]["qualifiedName"],
                             node["qualifiedName"].rsplit(".", 1)[0])

    def assert_java_service_imports(self, artifact, path) -> None:
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        imports = [nodes[edge["targetStableKey"]]["qualifiedName"] for edge in artifact.edges
                   if edge["type"] == "IMPORTS" and edge["sourceStableKey"] == f"file:{path}"]
        self.assertCountEqual(imports, [
            "brewing/Brewer.java::Brewer", "inventory/Inventory.java::Inventory",
            "inventory/Inventory.java::Inventory.Change", "external:java:java.util.ArrayList",
            "external:java:java.util.List", "external:java:java.util.Map",
            "external:java:java.util.function.Consumer",
        ])

    def assert_service_dependencies(self, artifact, path, extension) -> None:
        nodes = {node["stableKey"]: node for node in artifact.nodes}
        calls = [(nodes[edge["sourceStableKey"]]["qualifiedName"],
                  nodes[edge["targetStableKey"]]["qualifiedName"])
                 for edge in artifact.edges if edge["type"] == "CALLS"
                 and nodes[edge["sourceStableKey"]].get("path") == path
                 and nodes[edge["targetStableKey"]].get("path") == f"brewing/Brewer.{extension}"]
        self.assertCountEqual(calls, [
            (f"{path}::OrderService", f"brewing/Brewer.{extension}::Brewer")
            if extension == "kt" else
            (f"{path}::OrderService.OrderService", f"brewing/Brewer.{extension}::Brewer"),
            (f"{path}::OrderService.fulfill", f"brewing/Brewer.{extension}::Brewer.brew"),
            (f"{path}::OrderService.preview", f"brewing/Brewer.{extension}::Brewer.brew"),
        ])

    def test_reanalysis_reflects_source_changes_without_writing_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_application("typescript", Path(directory) / "project")
            source = root / "ordering/OrderService.ts"
            before = tree_contents(root)
            first = analyze_repository(root)
            self.assertEqual(tree_contents(root), before)
            changed = source.read_text().replace("function morningOrder(", "function openingOrder(")
            self.assertNotEqual(changed, source.read_text())
            source.write_text(changed)
            before[source.relative_to(root)] = source.read_bytes()
            second = analyze_repository(root)
            names = {node["name"] for node in second.nodes}
            self.assertIn("morningOrder", {node["name"] for node in first.nodes})
            self.assertNotIn("morningOrder", names)
            self.assertIn("openingOrder", names)
            self.assertEqual(second.stats, first.stats)
            self.assertEqual(tree_contents(root), before)

    def test_discovers_git_files_with_special_characters(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = copy_application("typescript", Path(directory) / "project")
            expected = {file.path for file in discover_files(root)} | {"café.ts", "a\nfile.ts"}
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            copyfile(root / "brewing/Brewer.ts", root / "café.ts")
            copyfile(root / "ordering/OrderService.ts", root / "a\nfile.ts")
            subprocess.run(["git", "-C", str(root), "add", "--", "café.ts"], check=True)
            external = Path(outside) / "private.ts"
            copyfile(root / "inventory/Inventory.ts", external)
            (root / "linked.ts").symlink_to(external)
            files = {file.path: file for file in discover_files(root)}
            self.assertEqual(set(files), expected)
            self.assertEqual(files["café.ts"].source, (root / "brewing/Brewer.ts").read_bytes())
            self.assertEqual(files["a\nfile.ts"].source, (root / "ordering/OrderService.ts").read_bytes())

    def test_discovers_large_and_non_programming_language_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_application("typescript", Path(directory) / "project")
            expected = {file.path for file in discover_files(root)} | {"notes.md", "payload.json"}
            order_source = (root / "ordering/Order.ts").read_text()
            payload = json.dumps({"order_source": order_source * (1_000_001 // len(order_source) + 1)})
            (root / "payload.json").write_text(payload)
            notes = f"# Coffee order model\n\n```typescript\n{order_source}\n```\n"
            (root / "notes.md").write_text(notes)
            (root / "node_modules").mkdir()
            copyfile(root / "brewing/Brewer.ts", root / "node_modules/ignored.ts")
            files = {file.path: file for file in discover_files(root)}
            self.assertEqual(set(files), expected)
            self.assertEqual(files["payload.json"].language, "json")
            self.assertEqual(files["notes.md"].language, "markdown")
            self.assertEqual(files["payload.json"].source, payload.encode())
            self.assertEqual(files["notes.md"].source, notes.encode())
            self.assertGreater(len(files["payload.json"].source), 1_000_000)


if __name__ == "__main__":
    unittest.main()
