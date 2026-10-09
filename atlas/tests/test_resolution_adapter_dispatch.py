"""Resolution policies dispatch by language, not shared resolver conditionals."""

import unittest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.resolver import resolve_connections
from tests.test_semantic_resolution import repository


class ResolutionAdapterDispatchTest(unittest.TestCase):
    def test_all_supported_languages_have_concrete_policies(self):
        expected = {
            "java": "JavaResolution",
            "kotlin": "KotlinResolution",
            "go": "GoResolution",
            "rust": "RustResolution",
            "javascript": "JavaScriptResolution",
            "jsx": "JavaScriptResolution",
            "typescript": "JavaScriptResolution",
            "tsx": "JavaScriptResolution",
            "elixir": "ElixirResolution",
            "python": "PythonResolution",
        }
        for language, class_name in expected.items():
            with self.subTest(language=language):
                adapter = get_resolution_adapter(language)
                self.assertEqual(type(adapter).__name__, class_name)
                self.assertIs(adapter, get_resolution_adapter(language))

    def test_python_comprehension_and_javascript_hoisting_are_separate_policies(self):
        python = get_resolution_adapter("python")
        javascript = get_resolution_adapter("javascript")
        self.assertIn("list_comprehension", python.scopes)
        self.assertNotIn("list_comprehension", javascript.scopes)
        self.assertIn("for_statement", python.loop_bindings)
        self.assertIn("variable_declarator", javascript.declarations)
        self.assertNotIn("variable_declarator", python.declarations)

    def test_tsx_namespace_reference_uses_qualified_import_and_shadowing(self):
        repo = repository(
            "tsx",
            {
                "Card.tsx": "export function Card() { return <div />; }",
                "App.tsx": """import * as Cards from './Card';
export function App() { return <Cards.Card />; }
export function Shadow(Cards: unknown) { return <Cards.Card />; }
""",
            },
        )
        references = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "REFERENCES"
        ]
        self.assertEqual(len(references), 2)
        self.assertEqual(
            sum(edge.target_key.startswith("symbol:") for edge in references), 1
        )
        self.assertEqual(
            sum(edge.target_key.startswith("external:") for edge in references), 1
        )


if __name__ == "__main__":
    unittest.main()
