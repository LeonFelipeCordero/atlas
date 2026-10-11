
from tests.source_snapshot_fixture import case_text
from tests.import_snapshot_support import write_import_case
import tempfile
import unittest
from pathlib import Path

from atlas.indexer import analyze_repository


class ImportResolutionTest(unittest.TestCase):
    def check_namespace(self, case_id: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, case_id)
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
        for index in range(1, 7):
            with self.subTest(case=index):
                self.check_namespace(f"namespace-{index}")

    def test_package_import_with_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            (root / "tools/a.go").write_text(case_text("imports", "import-resolution-package-import-with-multiple-files", 'tools/a.go'))
            (root / "tools/b.go").write_text(case_text("imports", "import-resolution-package-import-with-multiple-files", 'tools/b.go'))
            (root / "app.go").write_text(
                case_text("imports", "import-resolution-package-import-with-multiple-files", 'app.go')
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
        for index in range(1, 4):
            with self.subTest(case=index):
                self.check_shadowed_namespace(f"namespace-shadow-{index}")

    def check_shadowed_namespace(self, case_id) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, case_id)
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
        for index in range(1, 3):
            with self.subTest(case=index):
                self.check_ambiguous_namespace(f"namespace-ambiguous-{index}")

    def check_ambiguous_namespace(self, case_id) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, case_id)
            artifact = analyze_repository(root)
            calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
            self.assertTrue(calls)
            self.assertTrue(
                all(
                    str(edge["targetStableKey"]).startswith("external:")
                    for edge in calls
                )
            )
