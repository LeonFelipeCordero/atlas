import subprocess
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from atlas.parsing.discovery import discover_files
from atlas.indexer import analyze_repository


class IndexerTest(unittest.TestCase):
    def test_indexes_polyglot_symbols_and_connections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "helper.ts").write_text("export function helper() { return 1 }\n")
            (root / "service.ts").write_text(
                "import { helper } from './helper'\nexport class Service { run() { return helper() } }\n"
            )
            (root / "main.go").write_text(
                'package main\nimport "fmt"\nfunc main() { fmt.Println("hello") }\n'
            )
            (root / "App.java").write_text(
                "class App extends Base { void run() { helper(); } }\n"
            )
            (root / "App.kt").write_text(
                "class Clock : Base() { fun now() = Instant.now() }\n"
            )
            (root / "app.ex").write_text(
                "defmodule Demo do\n  def run(), do: Other.call()\nend\n"
            )
            artifact = analyze_repository(root)
            saved = asdict(artifact)

            self.assertEqual(artifact.stats["files"], 6)
            self.assertEqual(saved["schemaVersion"], 2)
            self.assertEqual(saved["stats"]["parseErrors"], 0)
            self.assertGreaterEqual(saved["stats"]["symbols"], 8)
            self.assert_polyglot_connections(saved)
            self.assert_service_node(saved)

    def assert_polyglot_connections(self, saved) -> None:
        self.assertTrue(
            any(
                edge["type"] == "IMPORTS"
                and edge["sourceStableKey"] == "file:service.ts"
                and edge["targetStableKey"] == "file:helper.ts"
                for edge in saved["edges"]
            )
        )
        self.assertTrue(
            any(
                edge["type"] == "CALLS"
                and "Service.run" in edge["sourceStableKey"]
                and "helper.ts::helper" in edge["targetStableKey"]
                for edge in saved["edges"]
            )
        )
        self.assert_connection_endpoints(saved)

    def assert_connection_endpoints(self, saved) -> None:
        keys = {node["stableKey"] for node in saved["nodes"]}
        self.assertTrue(
            all(
                edge["sourceStableKey"] in keys and edge["targetStableKey"] in keys
                for edge in saved["edges"]
            )
        )

    def assert_service_node(self, saved) -> None:
        service = next(node for node in saved["nodes"] if node["name"] == "Service")
        self.assertEqual(service["type"], "class")
        self.assertEqual(service["level"], "type")
        self.assertIn("file:service.ts", service["ancestorStableKeys"])

    def test_builds_module_file_type_and_callable_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            (root / "api").mkdir(parents=True)
            (root / "core").mkdir()
            (root / "core" / "helper.ts").write_text(
                "export class Helper { work() { return 1 } }\n"
            )
            (root / "api" / "service.ts").write_text(
                "import { Helper } from '../core/helper'\nexport class Service { run() { return work() } }\n"
            )

            artifact = analyze_repository(root)

            self.assertEqual(artifact.stats["modules"], 3)
            self.assertEqual(artifact.stats["types"], 2)
            self.assertEqual(artifact.stats["callables"], 2)
            module_edge = artifact.views["module"]["edges"][0]
            self.assertEqual(module_edge["sourceStableKey"], "module:api")
            self.assertEqual(module_edge["targetStableKey"], "module:core")
            self.assertEqual(
                module_edge["relationshipCounts"], {"CALLS": 1, "IMPORTS": 1}
            )
            file_edge = artifact.views["file"]["edges"][0]
            self.assertEqual(file_edge["sourceStableKey"], "file:api/service.ts")
            self.assertEqual(file_edge["targetStableKey"], "file:core/helper.ts")
            self.assertEqual(
                artifact.views["type"]["edges"][0]["relationshipCounts"], {"CALLS": 1}
            )
            self.assertEqual(
                artifact.views["callable"]["edges"][0]["relationshipCounts"],
                {"CALLS": 1},
            )

    def test_kotlin_class_methods_and_nested_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Service.kt").write_text("""package demo
interface Runner {
    fun run(): Int
}
class Service : Runner {
    override fun run(): Int {
        return helper()
    }
    fun run(value: Int): Int = value
    companion object {
        fun create(): Service = Service()
    }
    class Nested {
        fun work(): Int = helper()
    }
}
object Singleton {
    fun work(): Int = helper()
}
fun helper(): Int = 1
fun String.extension(): Int = helper()
""")
            artifact = analyze_repository(root)
            nodes = {
                node["qualifiedName"]: node
                for node in artifact.nodes
                if "qualifiedName" in node
            }
            methods = self.assert_kotlin_service_methods(artifact, nodes)
            self.assert_kotlin_callable_nodes(nodes)
            self.assert_kotlin_helper_call(artifact, nodes, methods)

    def assert_kotlin_service_methods(self, artifact, nodes):
        service = nodes["Service.kt::Service"]
        methods = [
            node
            for node in artifact.nodes
            if node["parentStableKey"] == service["stableKey"]
            and node["level"] == "callable"
        ]
        self.assertEqual([node["name"] for node in methods], ["run", "run"])
        self.assertEqual(len({node["stableKey"] for node in methods}), 2)
        self.assertEqual(nodes["Service.kt::Runner"]["kind"], "interface")
        return methods

    def assert_kotlin_callable_nodes(self, nodes) -> None:
        for name in [
            "Service.Companion.create",
            "Service.Nested.work",
            "Singleton.work",
            "Runner.run",
            "helper",
            "extension",
        ]:
            node = nodes[f"Service.kt::{name}"]
            self.assertEqual(node["level"], "callable")
            self.assertNotEqual(node["name"], "<anonymous>")

    def assert_kotlin_helper_call(self, artifact, nodes, methods) -> None:
        self.assertTrue(
            any(
                edge["type"] == "CALLS"
                and edge["sourceStableKey"] == methods[0]["stableKey"]
                and edge["targetStableKey"] == nodes["Service.kt::helper"]["stableKey"]
                for edge in artifact.edges
            )
        )

    def test_java_tags_add_constructors_without_losing_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Service.java").write_text("""package demo;
import demo.Other;
class Service {
    public Service() {}
    void run() {}
    void run(int value) {}
    class Nested { public Nested() {} }
}
""")
            artifact = analyze_repository(root)
            symbols = [node for node in artifact.nodes if "qualifiedName" in node]
            names = [node["qualifiedName"] for node in symbols]
            self.assertEqual(names.count("Service.java::Service.run"), 2)
            self.assertIn("Service.java::Service.Service", names)
            self.assertIn("Service.java::Service.Nested.Nested", names)
            self.assertIn("Service.java::demo", names)
            self.assertTrue(any(edge["type"] == "IMPORTS" for edge in artifact.edges))
            self.assertEqual(artifact.stats["parseErrors"], 0)

    def test_reanalysis_reflects_source_changes_without_writing_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            source = root / "main.ts"
            source.write_text("export function first() {}\n")
            first = analyze_repository(root)
            source.write_text("export function second() {}\n")
            second = analyze_repository(root)
            self.assertIn("first", {node["name"] for node in first.nodes})
            names = {node["name"] for node in second.nodes}
            self.assertNotIn("first", names)
            self.assertIn("second", names)
            self.assertEqual(list(root.iterdir()), [source])

    def test_discovers_git_files_with_special_characters(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as outside,
        ):
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "café.ts").write_text("export const value = 1\n")
            (root / "a\nfile.ts").write_text("export const value = 2\n")
            external = Path(outside) / "private.ts"
            external.write_text("export const secret = 3\n")
            (root / "linked.ts").symlink_to(external)

            self.assertEqual(
                {file.path for file in discover_files(root)},
                {"café.ts", "a\nfile.ts"},
            )

    def test_discovers_large_and_non_programming_language_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "payload.json").write_text('{"value":"' + "x" * 1_100_000 + '"}')
            (root / "notes.md").write_text("# Notes\n")
            dependencies = root / "node_modules"
            dependencies.mkdir()
            (dependencies / "ignored.ts").write_text("export const ignored = true\n")

            files = discover_files(root)

            self.assertEqual(
                {file.path for file in files}, {"notes.md", "payload.json"}
            )
            self.assertGreater(
                len(next(file.source for file in files if file.path == "payload.json")),
                1_000_000,
            )


if __name__ == "__main__":
    unittest.main()
