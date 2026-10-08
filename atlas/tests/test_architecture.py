"""Structural guard for the Python indexer's production modules."""

import ast
import unittest
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "atlas"
CONTROL = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)
BRANCH = CONTROL + (ast.ExceptHandler, ast.IfExp, ast.BoolOp)


def control_depth(node: ast.AST, current: int = 0, root: ast.AST | None = None) -> int:
    if (
        root is not None
        and node is not root
        and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    ):
        return current
    depth = current + isinstance(node, CONTROL)
    return max(
        [depth]
        + [
            control_depth(child, depth, root or node)
            for child in ast.iter_child_nodes(node)
        ]
    )


def module_dependencies(tree: ast.AST, modules: set[str], package: str) -> set[str]:
    """Resolve nested, absolute, and local imports, excluding type-only guards."""
    dependencies: set[str] = set()

    def visit(node: ast.AST) -> None:
        if is_type_checking_guard(node):
            return
        if isinstance(node, ast.ImportFrom):
            dependencies.update(relative_import_dependencies(node, modules, package))
        if isinstance(node, ast.Import):
            dependencies.update(alias.name for alias in node.names)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return dependencies & modules


def is_type_checking_guard(node: ast.AST) -> bool:
    return isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"


def relative_import_dependencies(node, modules, package):
    name = "." * node.level + (node.module or "")
    target = resolve_name(name, package) if node.level else name
    return {import_dependency(target, alias.name, modules) for alias in node.names}


def import_dependency(target, alias, modules):
    child = f"{target}.{alias}"
    return child if child in modules else target


def branch_complexity(node: ast.AST) -> int:
    return 1 + sum(is_complexity_branch(child) for child in ast.walk(node) if child is not node)


def is_complexity_branch(node: ast.AST) -> bool:
    return isinstance(node, BRANCH) or isinstance(node, ast.comprehension) and bool(node.ifs)


def assert_function_limits(test, node, label):
    test.assertLessEqual((node.end_lineno or node.lineno) - node.lineno + 1, 100, label)
    test.assertLessEqual(control_depth(node), 3, label)
    test.assertLessEqual(branch_complexity(node), 15, label)


def assert_tree_function_limits(test, tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert_function_limits(test, node, (name, node.name))


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["atlas", *parts])


def module_package(path: Path) -> str:
    name = module_name(path)
    return name if path.name == "__init__.py" else name.rpartition(".")[0]


class ArchitectureTest(unittest.TestCase):
    def test_dependency_scan_includes_local_and_package_imports(self) -> None:
        source = """\
from typing import TYPE_CHECKING
from . import java
from atlas.adapters.kotlin import KotlinResolution
import atlas.adapters.go
from ..domain.models import Symbol
if TYPE_CHECKING:
    from . import python

def resolve():
    from .rust import RustResolution
"""
        expected = {f"atlas.adapters.{name}" for name in ("java", "kotlin", "go", "rust")}
        expected.add("atlas.domain.models")
        modules = expected | {"atlas.adapters.python"}
        self.assertEqual(
            expected,
            module_dependencies(ast.parse(source), modules, "atlas.adapters"),
        )

    def test_package_imports_resolve_to_registry_or_child_module(self) -> None:
        modules = {"atlas.adapters", "atlas.adapters.java"}
        self.assertEqual(
            modules,
            module_dependencies(
                ast.parse("from ..adapters import get_adapter, java"),
                modules,
                "atlas.extraction",
            ),
        )

    def test_package_boundaries_exist(self) -> None:
        for package in ("adapters", "extraction", "domain", "cli"):
            self.assertTrue((ROOT / package / "__init__.py").is_file())
        self.assertEqual(
            {"__init__.py", "__main__.py", "bootstrap.py", "discovery.py", "indexer.py"},
            {path.name for path in ROOT.glob("*.py")},
        )

    def test_one_implementation_file_per_primary_language(self) -> None:
        primary = {
            "java",
            "kotlin",
            "go",
            "rust",
            "javascript",
            "typescript",
            "elixir",
            "python",
        }
        for language in primary:
            self.assertTrue((ROOT / "adapters" / f"{language}.py").is_file())
            self.assertEqual([], list((ROOT / "adapters").glob(f"{language}_*.py")))

    def test_adapters_do_not_depend_on_shared_graph_orchestration(self) -> None:
        forbidden = {
            "atlas.extraction.parser",
            "atlas.extraction.structure",
            "atlas.extraction.complexity",
            "atlas.domain.resolver",
            "atlas.domain.artifact",
            "atlas.domain.cycles",
            "atlas.indexer",
        }
        for path in (ROOT / "adapters").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            dependencies = module_dependencies(tree, forbidden, module_package(path))
            self.assertFalse(dependencies, str(path.relative_to(ROOT)))

    def test_module_size_function_size_and_relative_import_dag(self) -> None:
        files = {module_name(path): path for path in ROOT.rglob("*.py")}
        dependencies: dict[str, set[str]] = {}
        for name, path in files.items():
            source = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(source.splitlines()), 600, path.name)
            tree = ast.parse(source)
            assert_tree_function_limits(self, tree, name)
            dependencies[name] = module_dependencies(tree, set(files), module_package(path))

        visited: set[str] = set()

        def visit(name: str, active: tuple[str, ...]) -> None:
            self.assertNotIn(name, active, " -> ".join((*active, name)))
            if name in visited:
                return
            for target in dependencies[name]:
                visit(target, (*active, name))
            visited.add(name)

        for name in files:
            visit(name, ())


if __name__ == "__main__":
    unittest.main()
