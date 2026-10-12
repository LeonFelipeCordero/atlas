"""Exact whole-coffee import identities and isolated namespace/layout probes."""

import pytest

from atlas.metrics.resolver import resolve_connections
from tests.import_project_support import (
    assert_call, assert_external, edges_at, project_repository, project_sources,
    repository, symbols,
)


def coffee_repository(language):
    return project_repository(language)


def coffee_target_keys(repo, target):
    path, name = target
    return {symbol.key for symbol in symbols(repo, path, name)} if path else {name}


def assert_coffee_call(repo, case):
    path, owner, evidence, target_path, target_name = case
    owners = {symbol.key for symbol in symbols(repo, path, owner)}
    edges = [edge for edge in edges_at(repo, path, evidence) if edge.source_key in owners]
    targets = ({symbol.key for symbol in symbols(repo, target_path, target_name)}
               if target_path else {target_name})
    assert len(edges) == len(targets)
    assert {edge.target_key for edge in edges} == targets
    return edges


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


@pytest.mark.parametrize("case", [
    ("typescript", "roast-namespace", "brewing/preview.ts", 'roast.reserve("espresso")', "inventory/roast.ts", "reserve", "file:inventory/roast.ts"),
    ("javascript", "roast-namespace", "brewing/preview.js", 'roast.reserve("espresso")', "inventory/roast.js", "reserve", "file:inventory/roast.js"),
    ("go", "local-recipe-namespace", "brewing/tasting.go", 'recipe.Tasting("espresso")', "recipe/tasting.go", "Tasting", "module:recipe"),
])
def test_namespace_import_forms(case):
    language, variant, path, evidence, target_path, target_name, import_target = case
    repo = project_repository(language, variant)
    assert_call(repo, (path, evidence), (target_path, target_name))
    imports = [edge for edge in resolve_connections(repo).connections if edge.type == "IMPORTS" and edge.path == path]
    assert len(imports) == 1
    assert imports[0].target_key == import_target


@pytest.mark.parametrize("variant,evidence", [
    ("parameter-roast-namespace", 'roast.reserve("espresso")'),
    ("local-roast-namespace", 'roast.reserve("espresso")'),
    ("fluent-roast-namespace", 'roast.reserve("espresso").reserve("filter")'),
    ("reassigned-roast-namespace", 'roast.reserve("espresso")'),
    ("competing-roast-namespace", 'roast.reserve("espresso")'),
    ("unimported-roast-namespace", 'Unimported.reserve("espresso")'),
    ("ambiguous-roast-namespace", 'Ambiguous.reserve("espresso")'),
])
def test_unsafe_namespace_bindings_stay_unresolved(variant, evidence):
    repo = project_repository("typescript", variant)
    assert_external(repo, "brewing/preview.ts", evidence)


@pytest.mark.parametrize("variant", ["parameter-roast-namespace", "local-roast-namespace"])
def test_namespace_shadowing_does_not_poison_other_workflows(variant):
    repo = project_repository("typescript", variant)
    assert_call(repo, ("brewing/preview.ts", 'roast.reserve("filter")'), ("inventory/roast.ts", "reserve"))


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("multiple_files", [False, True])
def test_go_package_identity_and_explicit_alias(alias, multiple_files):
    sources = project_sources("go", "tasting-package-namespace")
    path = "brewing/tasting.go"
    if multiple_files:
        sources["tasting/aroma.go"] = "package tasting\nfunc Aroma() string { return \"coffee\" }\n"
    if alias:
        sources[path] = sources[path].replace('import "tasting"', 'import menu "tasting"').replace("tasting.Portions", "menu.Portions")
    repo = repository("go", sources)
    assert_call(repo, (path, ('menu' if alias else 'tasting') + '.Portions("espresso")'), ("tasting/menu.go", "Portions"))
    imports = [edge for edge in resolve_connections(repo).connections if edge.type == "IMPORTS" and edge.path == path]
    assert len(imports) == 1
    assert imports[0].target_key == ("module:tasting" if multiple_files else "file:tasting/menu.go")
