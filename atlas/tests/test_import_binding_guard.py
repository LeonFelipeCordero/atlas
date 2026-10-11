"""Selective imports must not be mistaken for namespace bindings."""

from tests.import_snapshot_support import import_case_sources as case_sources
from tests.source_snapshot_fixture import case_text

import unittest

from atlas.metrics.adapters.resolution import _namespace_binding
from atlas.metrics.resolver import resolve_connections
from tests.test_semantic_resolution import repository


class ImportBindingGuardTest(unittest.TestCase):
    def test_selective_and_from_imports_never_bind_module_namespace(self) -> None:
        for case_id, path in (("namespace-binding-guard-typescript", "sample.ts"), ("namespace-binding-guard-python", "sample.py")):
            source = case_text("imports", case_id, path)
            with self.subTest(source=source):
                self.assertIsNone(_namespace_binding(source, "tools"))

    def test_selective_import_resolves_export_but_not_unbound_module(self) -> None:
        for language in ("python", "typescript"):
            sources = case_sources("imports", "selective-import-" + language)
            with self.subTest(language=language):
                self.check_selective_import(language, sources)

    def check_selective_import(self, language, sources) -> None:
        graph = resolve_connections(repository(language, sources))
        calls = {
            edge.evidence: edge.target_key
            for edge in graph.connections
            if edge.type == "CALLS"
        }
        self.assertEqual(set(calls), {"tools.work()", "work()"})
        self.assertTrue(calls["tools.work()"].startswith("external:"))
        extension = "py" if language == "python" else "ts"
        self.assertTrue(calls["work()"].startswith(f"symbol:tools.{extension}::work:"))
