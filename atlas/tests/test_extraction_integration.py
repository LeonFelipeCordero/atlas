"""Grammar facts must reach resolution intact; unsafe syntax stays external."""

from tests.import_snapshot_support import import_case_sources as case_sources

from atlas.metrics.resolver import resolve_connections
from tests.test_semantic_resolution import ResolutionAssertions, call_edges, repository


class ExtractionIntegrationTest(ResolutionAssertions):
    def test_elixir_heads_controls_nested_arguments_and_pipelines(self):
        repo = repository(
            "elixir",
            case_sources("imports", "extraction-integration-elixir-heads-controls-nested-arguments-and-pipelines"),
        )
        calls = repo.files[0].calls
        self.assertEqual(
            [call.evidence for call in calls if call.name == "retry"], ["retry(n-1)"]
        )
        self.assertFalse(
            {"def", "defmodule", "if", "case"} & {call.name for call in calls}
        )
        for evidence in ("brew([])", "brew", "brew([1])", "brew([2])"):
            self.assertEqual(len(self.internal(repo, evidence, "Maker.brew")), 2)
        recursion = self.internal(repo, "retry(n-1)", "Maker.retry")
        self.assertEqual(len(recursion), 2)
        self.assertTrue(any(edge.source_key == edge.target_key for edge in recursion))

    def test_rust_macro_nested_arguments_offsets_and_invalid_dsl(self):
        repo = repository(
            "rust",
            case_sources("imports", "extraction-integration-rust-macro-nested-arguments-offsets-and-invalid-dsl"),
        )
        file = repo.files[0]
        inner = next(call for call in file.calls if call.name == "brew")
        self.assertEqual(inner.start_byte, file.source.source.rindex(b"brew()"))
        self.assertEqual(inner.line, 4)
        self.assertEqual(inner.evidence, "brew()")
        self.internal(repo, "brew()", "main.rs::brew")
        self.assertTrue(
            {"println!", "format!", "custom!"} <= {call.name for call in file.calls}
        )
        self.assertNotIn("missing", {call.name for call in file.calls})
        self.assertTrue(
            all(
                edge.target_key.startswith("external:")
                for edge in call_edges(repo)
                if edge.evidence and edge.evidence.startswith("custom!")
            )
        )

    def test_rust_relative_module_paths_keep_their_declared_identity(self):
        repo = repository(
            "rust",
            case_sources("imports", "extraction-integration-rust-relative-module-paths-keep-their-declared-identity"),
        )
        self.internal(repo, "crate::recipe::preview()", "recipe.rs::preview")
        self.internal(repo, "self::report::render()", "report.rs::render")
        imports = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "IMPORTS"
        ]
        self.assertEqual(len(imports), 2)
        self.assertTrue(all(edge.target_key.startswith("file:") for edge in imports))

    def test_inheritance_headers_and_import_aliases_are_precise(self):
        repo = repository(
            "python",
            case_sources("imports", "extraction-integration-inheritance-headers-and-import-aliases-are-precise"),
        )
        inherited = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "INHERITS"
        ]
        self.assertEqual(len(inherited), 1)
        self.assertIn("base.py::Base:", inherited[0].target_key)
        repo = repository(
            "java",
            case_sources("imports", "extraction-integration-inheritance-headers-and-import-aliases-are-precise-java"),
        )
        inherited = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "INHERITS"
        ]
        self.assertEqual(len(inherited), 1)
        self.assertTrue(inherited[0].target_key.startswith("external:"))

    def test_multiple_and_generic_bases_exclude_type_and_constructor_arguments(self):
        repo = repository(
            "python",
            case_sources("imports", "extraction-integration-multiple-and-generic-bases-exclude-type-and-constructor-arguments"),
        )
        self.assertEqual(
            [item.target_name for item in repo.inheritances], ["One", "Two"]
        )
