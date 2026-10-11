"""Exact whole-coffee import identities and isolated namespace/layout probes."""

import tempfile
import unittest
from pathlib import Path

import pytest

from atlas.indexer import analyze_repository
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_files
from tests.import_snapshot_support import write_import_case
from tests.test_semantic_resolution import (
    assert_coffee_call,
    call_edges,
    coffee_repository,
    coffee_symbols,
    coffee_target_keys,
)

COFFEE_IMPORTS = [
    ("python", "src/coffee/brewing/brewer.py", "from .recipe import Recipe", "src/coffee/brewing/recipe.py", None),
    ("python", "src/coffee/brewing/brewer.py", "from ..reporting.report import Report", "src/coffee/reporting/report.py", None),
    ("python", "src/coffee/brewing/brewer.py", "import coffee.brewing.recipe", "src/coffee/brewing/recipe.py", None),
    ("python", "src/coffee/brewing/brewer.py", "from coffee.brewing.recipe import portions as portion_count", "src/coffee/brewing/recipe.py", None),
    ("python", "src/coffee/brewing/brewer.py", "from . import (\n    recipe as relative_recipe,\n)", "src/coffee/brewing/recipe.py", None),
    ("python", "src/coffee/brewing/brewer.py", "from coffee.reporting import report as absolute_report", "src/coffee/reporting/report.py", None),
    ("python", "src/coffee/reporting/sales.py", "from .report import Report as CoffeeReport", "src/coffee/reporting/report.py", None),
    ("java", "orders/OrderService.java", "import coffee.brewing.Brewer;", "brewing/Brewer.java", "Brewer"),
    ("java", "inventory/Inventory.java", "import static coffee.brewing.Recipe.portions;", "brewing/Recipe.java", "Recipe.portions"),
    ("kotlin", "orders/OrderService.kt", "import coffee.brewing.Brewer as CoffeeBrewer", "brewing/Brewer.kt", "Brewer"),
    ("kotlin", "orders/Order.kt", "import coffee.reporting.render as renderCoffee", "reporting/Report.kt", "render"),
    ("javascript", "ordering/OrderService.js", 'import { Inventory } from "../inventory/Inventory.js";', "inventory/Inventory.js", None),
    ("typescript", "ordering/OrderService.ts", 'import { Inventory as BeanInventory } from "../inventory/Inventory.ts";', "inventory/Inventory.ts", None),
    ("typescript", "ordering/OrderService.ts", 'import type { Order as CoffeeOrder } from "./Order.ts";', "ordering/Order.ts", None),
    ("rust", "brewing/brewer.rs", "use self::brew as render_order;", "brewing/brewer.rs", "brew"),
    ("rust", "brewing/brewer.rs", "use super::recipe;", "brewing/recipe.rs", None),
    ("rust", "brewing/brewer.rs", "use crate::reporting::report;", "reporting/report.rs", None),
    ("rust", "reporting/daily/totals.rs", "use super::super::report as summary;", "reporting/report.rs", None),
    ("elixir", "brewing/order.ex", "alias Coffee.Brewing.Recipe, as: Drink", "brewing/recipe.ex", "Coffee.Brewing.Recipe"),
    ("elixir", "brewing/inventory.ex", "import Coffee.Brewing.Recipe, only: [portions: 1]", "brewing/recipe.ex", "Coffee.Brewing.Recipe"),
]


def coffee_import_edges(repo, site):
    path, evidence = site
    return [
        edge for edge in resolve_connections(repo).connections
        if edge.type == "IMPORTS" and edge.source_key == f"file:{path}" and edge.evidence == evidence
    ]


def assert_import_targets(repo, site, targets):
    path, evidence = site
    source = next(file.source.source.decode() for file in repo.files if file.source.path == path)
    assert evidence in source
    edges = coffee_import_edges(repo, site)
    assert len(edges) == len(targets)
    assert {edge.target_key for edge in edges} == targets


@pytest.mark.parametrize("case", COFFEE_IMPORTS)
def test_coffee_imports_reach_exact_declarations(case):
    language, path, evidence, target_path, target_name = case
    repo = coffee_repository(language)
    target = (target_path, target_name) if target_name else (None, f"file:{target_path}")
    assert_import_targets(repo, (path, evidence), coffee_target_keys(repo, target))


@pytest.mark.parametrize("evidence,target_path", [
    ("recipe.portions(name)", "src/coffee/brewing/recipe.py"),
    ("relative_recipe.portions(name)", "src/coffee/brewing/recipe.py"),
    ("portion_count(name)", "src/coffee/brewing/recipe.py"),
])
def test_coffee_python_namespace_and_aliased_calls(evidence, target_path):
    assert_coffee_call(coffee_repository("python"), ("src/coffee/brewing/brewer.py", "import_styles", evidence, target_path, "portions"))


def test_coffee_python_combined_module_aliases():
    repo = coffee_repository("python")
    path = "src/coffee/brewing/brewer.py"
    evidence = "import coffee.brewing.recipe as recipe, coffee.reporting.report as module_report"
    assert_import_targets(repo, (path, evidence), {
        "file:src/coffee/brewing/recipe.py", "file:src/coffee/reporting/report.py",
    })
    assert_coffee_call(repo, (path, "import_styles", "module_report.render([name])", "src/coffee/reporting/report.py", "render"))


def test_coffee_go_module_namespace_limit_is_explicit():
    # parse_files has no indexer's go.mod metadata enrichment. Never guess a
    # terminal package name; parent pipeline snapshots exercise enrichment.
    repo = coffee_repository("go")
    imports = [edge for edge in resolve_connections(repo).connections if edge.type == "IMPORTS" and edge.evidence == 'menu "example.com/coffee/recipe"']
    assert len(imports) == 1
    assert imports[0].target_key == "external:go:module:example.com/coffee/recipe"
    assert_coffee_call(repo, ("brewing/brewer.go", "score", "menu.Portions(name)", None, "external:go:callable:Portions"))


class ImportResolutionTest(unittest.TestCase):
    def test_namespace_import_forms_absent_from_coffee(self):
        # Bare Go package paths and JS/TS `import *` are absent from those coffee
        # projects. TSX namespace tags are a different grammar/relationship.
        cases = [
            ("namespace-1", "tools/worker.go", "Work", "tools.Work()", "file:tools/worker.go"),
            ("namespace-2", "tools/worker.go", "Work", "worker.Work()", "file:tools/worker.go"),
            ("namespace-5", "tools.ts", "work", "tools.work()", "file:tools.ts"),
            ("namespace-6", "tools.js", "work", "worker.work()", "file:tools.js"),
            ("import-resolution-package-import-with-multiple-files", "tools/a.go", "Work", "tools.Work()", "module:tools"),
        ]
        for case in cases:
            with self.subTest(case=case[0]):
                self.check_retained_namespace(case)

    def check_retained_namespace(self, case):
        case_id, path, name, evidence, import_target = case
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, case_id)
            repo = parse_files(discover_files(root))
            target, = coffee_symbols(repo, path, name)
            calls = call_edges(repo, evidence)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].target_key, target.key)
            imports = [edge for edge in resolve_connections(repo).connections if edge.type == "IMPORTS"]
            self.assertEqual(len(imports), 1)
            self.assertEqual(imports[0].target_key, import_target)

    def test_shadowed_namespace_and_fluent_result_stay_unresolved(self) -> None:
        for index in range(1, 4):
            with self.subTest(case=index):
                self.check_unresolved_namespace(f"namespace-shadow-{index}")

    def test_unimported_or_ambiguous_namespace_does_not_resolve(self) -> None:
        for index in range(1, 3):
            with self.subTest(case=index):
                self.check_unresolved_namespace(f"namespace-ambiguous-{index}")

    def check_unresolved_namespace(self, case_id) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, case_id)
            artifact = analyze_repository(root)
            calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
            self.assertTrue(calls)
            self.assertTrue(all(str(edge["targetStableKey"]).startswith("external:") for edge in calls))
