"""Resolution policies dispatch by language, not shared resolver conditionals."""

import unittest
from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources


class ResolutionAdapterDispatchTest(unittest.TestCase):
    def test_all_supported_languages_have_concrete_policies(self):
        expected = {
            "java": "JavaResolution",
            "kotlin": "KotlinResolution",
            "go": "GoResolution",
            "rust": "RustResolution",
            "javascript": "JavaScriptResolution",
            "jsx": "JavaScriptResolution",
            "typescript": "TypeScriptResolution",
            "tsx": "TypeScriptResolution",
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
        repo = parse_files(coffee_sources("tsx"))
        owners, target = component_keys(repo)
        references = app_references(repo)
        qualified = [edge for edge in references if edge.evidence == "Cards.CoffeeCard"]
        self.assertEqual(len(qualified), 1)
        self.assertEqual((qualified[0].source_key, qualified[0].target_key),
                         (owners["App"], target))
        shadowed = [edge for edge in references if edge.source_key == owners["Preview"]]
        self.assertEqual(len(shadowed), 1)
        self.assertEqual((shadowed[0].evidence, shadowed[0].target_key),
                         ("CoffeeCard", "external:tsx:callable:CoffeeCard"))


def component_keys(repo):
    app = next(file for file in repo.files if file.source.path == "App.tsx")
    card = next(file for file in repo.files if file.source.path == "CoffeeCard.tsx")
    target, = [symbol.key for symbol in card.symbols if symbol.name == "CoffeeCard"]
    return {symbol.name: symbol.key for symbol in app.symbols}, target


def app_references(repo):
    return [edge for edge in resolve_connections(repo).connections
            if edge.type == "REFERENCES" and edge.path == "App.tsx"]


if __name__ == "__main__":
    unittest.main()
