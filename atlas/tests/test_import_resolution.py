import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from atlas.indexer import analyze_repository


@dataclass(frozen=True)
class NamespaceCase:
    extension: str
    definition: str
    usage: str
    folder: bool = False


class ImportResolutionTest(unittest.TestCase):
    def check_namespace(self, case: NamespaceCase) -> None:
        extension, definition, usage, folder = case.extension, case.definition, case.usage, case.folder
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / (
                f"tools/worker.{extension}" if folder else f"tools.{extension}"
            )
            target.parent.mkdir(exist_ok=True)
            target.write_text(definition)
            (root / f"app.{extension}").write_text(usage)
            artifact = analyze_repository(root)
            calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
            self.assertTrue(
                any(
                    "tools" in str(edge["targetStableKey"])
                    and str(edge["targetStableKey"]).startswith("symbol:")
                    for edge in calls
                )
            )
            self.assertTrue(
                any(
                    edge["type"] == "IMPORTS"
                    and not str(edge["targetStableKey"]).startswith("external:")
                    for edge in artifact.edges
                )
            )

    def test_namespace_imports_across_grammars(self) -> None:
        cases = [
            (
                "go",
                "package tools\nfunc Work() {}",
                'package main\nimport "tools"\nfunc run(){ tools.Work() }',
                True,
            ),
            (
                "go",
                "package tools\nfunc Work() {}",
                'package main\nimport worker "tools"\nfunc run(){ worker.Work() }',
                True,
            ),
            ("py", "def work(): pass", "import tools\ntools.work()", False),
            ("py", "def work(): pass", "import tools as worker\nworker.work()", False),
            (
                "ts",
                "export function work() {}",
                "import * as tools from './tools'; tools.work()",
                False,
            ),
            (
                "js",
                "export function work() {}",
                "import * as worker from './tools'; worker.work()",
                False,
            ),
        ]
        for case in cases:
            with self.subTest(extension=case[0], usage=case[2]):
                self.check_namespace(NamespaceCase(*case))

    def test_package_import_with_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            (root / "tools/a.go").write_text("package tools\nfunc Work() {}")
            (root / "tools/b.go").write_text("package tools\nfunc Other() {}")
            (root / "app.go").write_text(
                'package main\nimport "tools"\nfunc run(){ tools.Work() }'
            )
            artifact = analyze_repository(root)
            self.assertTrue(
                any(
                    edge["type"] == "IMPORTS"
                    and edge["targetStableKey"] == "module:tools"
                    for edge in artifact.edges
                )
            )
            self.assertTrue(
                any(
                    edge["type"] == "CALLS"
                    and "tools/a.go::Work" in str(edge["targetStableKey"])
                    for edge in artifact.edges
                )
            )

    def test_shadowed_namespace_and_fluent_result_stay_unresolved(self) -> None:
        usages = [
            "function run(tools) { tools.work() }",
            "tools = other; tools.work()",
            "tools.factory().work()",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                self.check_shadowed_namespace(usage)

    def check_shadowed_namespace(self, usage) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools.ts").write_text("export function work() {}")
            (root / "app.ts").write_text("import * as tools from './tools'; " + usage)
            artifact = analyze_repository(root)
            calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
            self.assertTrue(calls)
            self.assertTrue(
                all(
                    str(edge["targetStableKey"]).startswith("external:")
                    for edge in calls
                )
            )

    def test_unimported_or_ambiguous_namespace_does_not_resolve(self) -> None:
        for imports in (
            "",
            "import * as tools from './a'; import * as tools from './b';",
        ):
            with self.subTest(imports=imports):
                self.check_ambiguous_namespace(imports)

    def check_ambiguous_namespace(self, imports) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a", "b"):
                (root / f"{name}.ts").write_text("export function work() {}")
            (root / "app.ts").write_text(imports + "tools.work()")
            artifact = analyze_repository(root)
            calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
            self.assertTrue(calls)
            self.assertTrue(
                all(
                    str(edge["targetStableKey"]).startswith("external:")
                    for edge in calls
                )
            )
