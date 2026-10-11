"""Structural guard for the Python indexer's production modules."""

import ast
import unittest
from importlib.util import resolve_name
from itertools import product
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
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
    )


def relative_import_dependencies(node, modules, package):
    name = "." * node.level + (node.module or "")
    target = resolve_name(name, package) if node.level else name
    return {import_dependency(target, alias.name, modules) for alias in node.names}


def import_dependency(target, alias, modules):
    child = f"{target}.{alias}"
    return child if child in modules else target


def branch_complexity(node: ast.AST) -> int:
    return 1 + sum(
        is_complexity_branch(child) for child in ast.walk(node) if child is not node
    )


def is_complexity_branch(node: ast.AST) -> bool:
    return (
        isinstance(node, BRANCH)
        or isinstance(node, ast.comprehension)
        and bool(node.ifs)
    )


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
    def test_package_boundaries_exist(self) -> None:
        for package in (
            "parsing",
            "parsing/adapters",
            "metrics",
            "metrics/adapters",
            "domain",
            "cli",
        ):
            self.assertTrue((ROOT / package / "__init__.py").is_file())
        self.assertEqual(
            {
                "__init__.py",
                "__main__.py",
                "bootstrap.py",
                "syntax.py",
                "language_syntax.py",
                "indexer.py",
            },
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
        for phase, language in product(("parsing", "metrics"), primary):
            root = ROOT / phase / "adapters"
            self.assertTrue((root / f"{language}.py").is_file())
            self.assertEqual([], list(root.glob(f"{language}_*.py")))

    def test_adapters_do_not_depend_on_shared_graph_orchestration(self) -> None:
        forbidden = {
            "atlas.parsing.parser",
            "atlas.parsing.structure",
            "atlas.metrics.complexity",
            "atlas.metrics.callables",
            "atlas.metrics.resolver",
            "atlas.metrics.artifact",
            "atlas.metrics.cycles",
            "atlas.indexer",
        }
        for path in ROOT.glob("*/adapters/**/*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            dependencies = module_dependencies(tree, forbidden, module_package(path))
            self.assertFalse(dependencies, str(path.relative_to(ROOT)))

    def test_phase_adapters_and_shared_models_are_independent(self) -> None:
        files = {module_name(path): path for path in ROOT.rglob("*.py")}
        for phase, other in (("parsing", "metrics"), ("metrics", "parsing")):
            self.assert_package_independent(
                ROOT / phase, files, f"atlas.{other}.adapters"
            )
        self.assert_package_independent(
            ROOT / "domain", files, ("atlas.parsing", "atlas.metrics")
        )

    def assert_package_independent(self, root, files, prefixes):
        forbidden = {name for name in files if name.startswith(prefixes)}
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            self.assertFalse(
                module_dependencies(tree, forbidden, module_package(path)),
                str(path.relative_to(ROOT)),
            )

    def test_module_size_function_size_and_relative_import_dag(self) -> None:
        files = {module_name(path): path for path in ROOT.rglob("*.py")}
        dependencies: dict[str, set[str]] = {}
        for name, path in files.items():
            source = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(source.splitlines()), 600, path.name)
            tree = ast.parse(source)
            assert_tree_function_limits(self, tree, name)
            dependencies[name] = module_dependencies(
                tree, set(files), module_package(path)
            )

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
