"""Keep language decisions behind adapters, including future nested modules."""

import ast
import unittest
from pathlib import Path

from tests.test_architecture import assert_tree_function_limits

ROOT = Path(__file__).resolve().parents[1] / "src/atlas"
LANGUAGES = {
    "java",
    "kotlin",
    "go",
    "rust",
    "python",
    "elixir",
    "javascript",
    "typescript",
    "tsx",
    "jsx",
}


def language_literals(node):
    return {
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value in LANGUAGES
    }


def forbidden_adapter_modules():
    return LANGUAGES | {
        f"atlas.{phase}.adapters.{language}"
        for phase in ("parsing", "metrics") for language in LANGUAGES
    }


class AdapterBoundaryTest(unittest.TestCase):
    def assert_shared_engine_node(self, path, node):
        if isinstance(node, ast.ImportFrom) and node.module:
            self.assertNotIn(node.module, forbidden_adapter_modules(), (path.name, node.lineno, node.module))
        if not isinstance(node, ast.Compare):
            return
        languages = language_literals(node)
        self.assertFalse(languages, (path.name, node.lineno, languages))

    def assert_shared_engine_file(self, path):
        for node in ast.walk(ast.parse(path.read_text())):
            self.assert_shared_engine_node(path, node)

    def test_shared_engines_do_not_dispatch_on_language_names(self):
        files = [
            ROOT / name
            for name in (
                "parsing/parser.py",
                "parsing/structure.py",
                "metrics/complexity.py",
                "metrics/callables.py",
                "metrics/resolution_syntax.py",
                "metrics/resolver.py",
                "metrics/adapters/resolution.py",
            )
        ]
        for path in files:
            self.assert_shared_engine_file(path)

    def test_nested_adapter_modules_obey_size_limits(self):
        for path in ROOT.rglob("*.py"):
            source = path.read_text()
            self.assertLessEqual(
                len(source.splitlines()), 600, str(path.relative_to(ROOT))
            )
            assert_tree_function_limits(self, ast.parse(source), str(path.relative_to(ROOT)))


if __name__ == "__main__":
    unittest.main()
