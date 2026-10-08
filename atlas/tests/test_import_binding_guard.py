"""Selective imports must not be mistaken for namespace bindings."""

import unittest

from atlas.adapters.resolution import _namespace_binding
from atlas.domain.resolver import resolve_connections
from tests.test_semantic_resolution import repository


class ImportBindingGuardTest(unittest.TestCase):
    def test_selective_and_from_imports_never_bind_module_namespace(self) -> None:
        for source in ("import {work} from './tools'", "from tools import work"):
            with self.subTest(source=source):
                self.assertIsNone(_namespace_binding(source, "tools"))

    def test_selective_import_resolves_export_but_not_unbound_module(self) -> None:
        for language, sources in (
            (
                "python",
                {
                    "tools.py": "def work(): pass",
                    "main.py": "from tools import work\ntools.work()\nwork()",
                },
            ),
            (
                "typescript",
                {
                    "tools.ts": "export function work() {}",
                    "main.ts": "import {work} from './tools'; tools.work(); work();",
                },
            ),
        ):
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
