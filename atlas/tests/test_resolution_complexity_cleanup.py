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
from atlas.metrics.resolution_syntax import (
    SCOPES as SYNTAX_SCOPES,
    Syntax,
    names,
)
from atlas.syntax import walk
from tests.test_architecture import module_dependencies, module_name
from tests.test_semantic_resolution import repository

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
        module and module.endswith("resolution_syntax") for module in imports
    )


def test_js_export_deduplication_preserves_alias_keys_and_order():
    repo = repository(
        "typescript",
        {
            "api.ts": """
function hidden() {}
export {hidden as api};
export {hidden as api, hidden as default};
export {type hidden as TypeOnly};
export type {hidden as OtherType};
export {hidden as remote} from './elsewhere';
"""
        },
    )
    file = repo.files[0]
    exports = export_bindings(file, Syntax(file, get_resolution_adapter("typescript")))
    assert list(exports) == ["api", "default"]
    assert exports["api"] == exports["default"]
    assert [symbol.name for symbol in exports["api"]] == ["hidden"]


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("(((work)))", "identifier"),
        ("(work, other)", "sequence_expression"),
        ("(/* comment */ work)", "identifier"),
    ],
)
def test_parentheses_only_unwrap_single_expressions(expression, expected):
    root = get_parser("javascript").parse(expression.encode()).root_node
    assert unparenthesized(root.named_children[0].named_children[0]).type == expected


def test_import_directives_on_one_line_keep_exact_source_selection():
    repo = repository(
        "typescript", {"main.ts": "import {a} from './a'; import {b} from './b';"}
    )
    syntax = Syntax(repo.files[0], get_resolution_adapter("typescript"))
    assert syntax.import_node(1) is None
    selected = syntax.import_node(1, "import {b} from './b'")
    assert selected is not None and selected.text == b"import {b} from './b';"


def test_recursive_binding_names_still_ignore_types_and_member_targets():
    root = (
        get_parser("typescript")
        .parse(b"const {key: renamed, other} = source;")
        .root_node
    )
    pattern = next(node for node in walk(root) if node.type == "object_pattern")
    assert names(pattern) == {"renamed", "other"}
    member = (
        get_parser("typescript")
        .parse(b"source.member;")
        .root_node.named_children[0]
        .named_children[0]
    )
    assert names(member) == set()
