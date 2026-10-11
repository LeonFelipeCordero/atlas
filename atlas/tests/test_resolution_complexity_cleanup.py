"""Budget and semantic regressions for resolution-policy helper extraction."""

import ast
from pathlib import Path
import pytest
from tree_sitter_language_pack import get_parser
from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.javascript import export_bindings
from atlas.parsing.adapters.javascript import unparenthesized
from atlas.metrics.adapters.resolution import ResolutionAdapter
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter as Policy
from atlas.metrics.complexity import calculate_complexity
from atlas.metrics.resolution_contract import SCOPES
from atlas.metrics.resolution_syntax import SCOPES as SYNTAX_SCOPES, Syntax, names
from atlas.syntax import walk
from tests.test_architecture import module_dependencies, module_name
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources
from tests.variant_snapshot_support import VARIANT_ROOT, scenario_sources

ROOT = Path(__file__).parents[1] / "src" / "atlas"
OWNED = (
    "metrics/adapters/javascript.py",
    "metrics/adapters/rust.py",
    "metrics/adapters/resolution.py",
    "metrics/adapters/resolution_policy.py",
    "metrics/adapters/resolution_paths.py",
    "metrics/adapters/module_index.py",
    "metrics/adapters/__init__.py",
    "metrics/resolution_syntax.py",
    "metrics/resolution_contract.py",
)


@pytest.mark.parametrize("relative", OWNED)
def test_resolution_callable_budgets(relative):
    path = ROOT / relative
    assert len(path.read_text().splitlines()) <= 600
    root = get_parser("python").parse(path.read_bytes()).root_node
    assert not root.has_error
    for node in walk(root):
        if node.type == "function_definition":
            _assert_budget(relative, node)


def _assert_budget(relative, node):
    label = f"{relative}:{node.start_point.row + 1}"
    metrics = calculate_complexity(node)
    assert metrics.cyclomaticComplexity <= 8, label
    assert metrics.loopNestedComplexity == 0, label
    assert metrics.maxDecisionDepth <= 3, label
    assert node.end_point.row - node.start_point.row < 100, label


def test_policy_and_scope_reexports_keep_the_same_objects():
    assert ResolutionAdapter is Policy
    assert SCOPES is SYNTAX_SCOPES


def test_registry_relative_imports_target_children_not_itself():
    modules = {module_name(path) for path in ROOT.rglob("*.py")}
    tree = ast.parse((ROOT / "metrics/adapters/__init__.py").read_text())
    dependencies = module_dependencies(tree, modules, "atlas.metrics.adapters")
    assert "atlas.metrics.adapters" not in dependencies
    assert {
        "atlas.metrics.adapters.javascript",
        "atlas.metrics.adapters.rust",
    } <= dependencies


def test_syntax_type_dependency_targets_independent_policy_contract():
    tree = ast.parse((ROOT / "metrics/resolution_syntax.py").read_text())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert "adapters.resolution_policy" in imports
    assert "adapters.resolution" not in imports
    _assert_no_syntax_dependency("metrics/adapters/resolution_policy.py")
    _assert_no_syntax_dependency("metrics/adapters/resolution_paths.py")
    _assert_no_syntax_dependency("metrics/resolution_contract.py")


def _assert_no_syntax_dependency(relative):
    tree = ast.parse((ROOT / relative).read_text())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        (module and module.endswith("resolution_syntax") for module in imports)
    )


def lexical_repository():
    return parse_files(scenario_sources(VARIANT_ROOT / "typescript/lexical-orders"))


def test_js_export_deduplication_preserves_alias_keys_and_order():
    repo = lexical_repository()
    file = next(file for file in repo.files
                if file.source.path == "reporting/SeasonalReceipt.ts")
    exports = export_bindings(file, Syntax(file, get_resolution_adapter("typescript")))
    assert list(exports) == ["receipt", "default"]
    assert exports["receipt"] == exports["default"]
    symbol, = exports["receipt"]
    assert symbol.name == "seasonalReceipt"
    assert symbol is next(symbol for symbol in file.symbols
                          if symbol.name == "seasonalReceipt")


@pytest.mark.parametrize("language", ["javascript", "typescript"])
def test_parentheses_only_unwrap_single_expressions(language):
    repo = parse_files(coffee_sources(language))
    observed = set()
    for file in repo.files:
        observed.update(parenthesized_types(file))
    assert {"arrow_function", "function_expression", "generator_function",
            "identifier", "member_expression"} <= observed


def parenthesized_types(file):
    root = Syntax(file, get_resolution_adapter(file.source.language)).root
    assert root is not None and not root.has_error
    return {assert_transparent_expression(node).type for node in walk(root)
            if node.type == "parenthesized_expression"}


def assert_transparent_expression(node):
    result = unparenthesized(node)
    children = [child for child in node.named_children if child.type != "comment"]
    expected = unparenthesized(children[0]) if len(children) == 1 else node
    assert result == expected
    assert result.start_byte >= node.start_byte
    assert result.end_byte <= node.end_byte
    assert unparenthesized(result) == result
    return result


def test_import_directives_keep_exact_source_selection():
    repo = parse_files(coffee_sources("typescript"))
    file = next(file for file in repo.files if file.source.path == "reporting/Receipt.ts")
    syntax = Syntax(file, get_resolution_adapter("typescript"))
    assert syntax.import_node(4) is None
    selected = syntax.import_node(2, 'import { priceOrder } from "../ordering/Orders.ts"')
    assert selected is not None
    assert selected.text == b'import { priceOrder } from "../ordering/Orders.ts";'
    assert syntax.import_node(2) == selected
    assert syntax.import_node(2, 'import { Recipe } from "../brewing/Recipe.ts"') == selected


@pytest.mark.parametrize("pattern,expected", [
    ("{seasonal: {Drink}}", {"Drink"}),
    ("{recipe: Drink}", {"Drink"}),
    ("{label, ...Drink}", {"label", "Drink"}),
    ("{recipe: Drink = recipes[0]}", {"Drink"}),
    ("{Drink: seasonal}", {"seasonal"}),
])
def test_recursive_binding_names_still_ignore_types_and_member_targets(pattern, expected):
    repo = lexical_repository()
    file = next(file for file in repo.files if file.source.path == "ordering/LexicalOrders.ts")
    root = Syntax(file, get_resolution_adapter("typescript")).root
    assert root is not None and not root.has_error
    assert names(syntax_node(root, ("object_pattern", pattern.encode()))) == expected
    assert names(syntax_node(root, ("required_parameter", b"Drink: unknown"))) == {"Drink"}
    assert_member_targets_have_no_bindings(root)


def syntax_node(root, identity):
    kind, text = identity
    return next(node for node in walk(root) if node.type == kind and node.text == text)


def assert_member_targets_have_no_bindings(root):
    members = [node for node in walk(root) if node.type == "member_expression"]
    assert members
    assert all(names(member) == set() for member in members)
