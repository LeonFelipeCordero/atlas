"""Source-grounded coffee resolution and isolated ambiguity/grammar regressions."""

import unittest

import pytest

from tests.coffee_fixture import FIXTURE_ROOT
from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_files
from atlas.metrics.resolver import resolve_connections


def repository(language, sources):
    from tests.import_project_support import repository as parse_project
    return parse_project(language, sources)


def call_edges(repo, evidence=None):
    edges = [e for e in resolve_connections(repo).connections if e.type == "CALLS"]
    return [e for e in edges if e.evidence == evidence] if evidence else edges


def coffee_repository(language):
    return parse_files(discover_files(FIXTURE_ROOT / language))


def coffee_symbols(repo, path, name):
    symbols = [
        symbol for file in repo.files if file.source.path == path
        for symbol in file.symbols if symbol.qualified_name == f"{path}::{name}"
    ]
    assert symbols, (path, name)
    return symbols


def coffee_target_keys(repo, target):
    path, name = target
    if path:
        return {symbol.key for symbol in coffee_symbols(repo, path, name)}
    return {name}


def coffee_owner_keys(repo, owner):
    path, name = owner
    if name:
        return coffee_target_keys(repo, owner)
    return {f"file:{path}"}


def assert_call_source(repo, site):
    path, evidence = site
    file = next(file for file in repo.files if file.source.path == path)
    sites = [call for call in file.calls if call.evidence == evidence]
    assert sites, site
    assert all(file.source.source[call.start_byte:call.end_byte].decode() == evidence for call in sites)


def assert_coffee_call(repo, case):
    """Compare exact parsed identities, not terminal-name substrings or snapshots."""
    path, owner, evidence, target_path, target_name = case
    assert_call_source(repo, (path, evidence))
    owners = coffee_owner_keys(repo, (path, owner))
    edges = [edge for edge in call_edges(repo, evidence) if edge.source_key in owners]
    targets = coffee_target_keys(repo, (target_path, target_name))
    assert len(edges) == len(targets), (case, edges)
    assert {edge.target_key for edge in edges} == targets
    return edges


SEMANTIC_CALLS = [
    ("python", "src/coffee/brewing/brewer.py", "Brewer.brew", "Recipe.portions(name)", "src/coffee/brewing/recipe.py", "Recipe.portions"),
    ("python", "src/coffee/brewing/brewer.py", "Brewer.brew", "Report.render([])", "src/coffee/reporting/report.py", "Report.render"),
    ("python", "src/coffee/brewing/brewer.py", "import_styles", "coffee.brewing.recipe.portions(name)", "src/coffee/brewing/recipe.py", "portions"),
    ("python", "src/coffee/brewing/brewer.py", "main", 'Brewer().brew(["espresso", "filter", "invalid"])', "src/coffee/brewing/brewer.py", "Brewer.brew"),
    ("python", "src/coffee/brewing/brewer.py", "main", "Brewer()", "src/coffee/brewing/brewer.py", "Brewer"),
    ("python", "src/coffee/reporting/sales.py", "SalesReport.render", "CoffeeReport.render(names)", "src/coffee/reporting/report.py", "Report.render"),
    ("java", "brewing/Brewer.java", "Brewer.brew.<anonymous>", "Recipe.portions(name)", "brewing/Recipe.java", "Recipe.portions"),
    ("java", "inventory/Inventory.java", "Inventory.reserve", "portions(line.drink)", "brewing/Recipe.java", "Recipe.portions"),
    ("kotlin", "orders/Order.kt", "receipt", "renderCoffee(names())", "reporting/Report.kt", "render"),
    ("kotlin", "orders/OrderService.kt", "OrderService", "CoffeeBrewer()", "brewing/Brewer.kt", "Brewer"),
    ("kotlin", "brewing/Brewer.kt", "main", 'Brewer().brew(listOf("espresso", "filter", "invalid"))', "brewing/Brewer.kt", "Brewer.brew"),
    ("javascript", "brewing/Brewer.js", "Brewer.brew.<anonymous>", "Recipe.portions(name)", "brewing/Recipe.js", "Recipe.portions"),
    ("javascript", "brewing/Brewer.js", "main", 'new Brewer().brew(["espresso", "filter", "invalid"])', "brewing/Brewer.js", "Brewer.brew"),
    ("typescript", "brewing/Brewer.ts", "Brewer.brew.<anonymous>", "Recipe.portions(name)", "brewing/Recipe.ts", "Recipe.portions"),
    ("typescript", "brewing/Brewer.ts", "main", 'new Brewer().brew(["espresso", "filter", "invalid"])', "brewing/Brewer.ts", "Brewer.brew"),
    ("typescript", "ordering/OrderService.ts", "morningOrder", "new BeanInventory()", "inventory/Inventory.ts", "Inventory"),
    ("rust", "brewing/brewer.rs", "brew", "report::render(&[])", "reporting/report.rs", "render"),
    ("rust", "brewing/brewer.rs", "brew.<anonymous>", "recipe::portions(name)", "brewing/recipe.rs", "portions"),
    ("rust", "brewing/brewer.rs", "Brewer.brew", "render_order(&available)", "brewing/brewer.rs", "brew"),
    ("rust", "main.rs", "main", 'crate::brewing::recipe::preview("espresso")', "brewing/recipe.rs", "preview"),
    ("rust", "reporting/daily/totals.rs", "portions", "summary::total(names)", "reporting/report.rs", "total"),
    ("elixir", "brewing/order.ex", "Coffee.Brewing.Order.preview", "Receipt.render(names)", "reporting/report.ex", "Coffee.Reporting.Report.render"),
    ("elixir", "brewing/order.ex", "Coffee.Brewing.Order.estimate", "Drink.scale(&1, multiplier)", "brewing/recipe.ex", "Coffee.Brewing.Recipe.scale"),
    ("elixir", "brewing/inventory.ex", "Coffee.Brewing.Inventory.reserve", "portions(name)", "brewing/recipe.ex", "Coffee.Brewing.Recipe.portions"),
]


@pytest.mark.parametrize("case", SEMANTIC_CALLS)
def test_coffee_static_imported_and_constructed_calls(case):
    language, *call = case
    assert_coffee_call(coffee_repository(language), call)


RECURSIVE_CALLS = [
    ("python", "src/coffee/brewing/brewer.py", "Brewer.retry", "self.retry(attempts - 1)"),
    ("java", "brewing/Brewer.java", "Brewer.retry", "retry(attempts - 1)"),
    ("kotlin", "brewing/Brewer.kt", "Brewer.retry", "retry(attempts - 1)"),
    ("javascript", "brewing/Brewer.js", "Brewer.retry", "this.retry(attempts - 1)"),
    ("typescript", "brewing/Brewer.ts", "Brewer.retry", "this.retry(attempts - 1)"),
    ("go", "brewing/brewer.go", "retry", "retry(attempts-1)"),
    ("rust", "brewing/brewer.rs", "retry", "retry(attempts - 1)"),
    ("elixir", "brewing/brewer.ex", "Coffee.Brewing.Brewer.retry", "retry(attempts - 1)"),
]


@pytest.mark.parametrize("case", RECURSIVE_CALLS)
def test_coffee_recursion_preserves_declaration_identity(case):
    language, path, owner, evidence = case
    repo = coffee_repository(language)
    edges = assert_coffee_call(repo, (path, owner, evidence, path, owner))
    assert sum(edge.source_key == edge.target_key for edge in edges) == 1
    assert len(edges) == (2 if language == "elixir" else 1)


def test_coffee_go_named_closure_ownership_and_target():
    repo = coffee_repository("go")
    owner, = coffee_symbols(repo, "brewing/brewer.go", "brew")
    closure, = coffee_symbols(repo, "brewing/brewer.go", "brew.accept")
    assert closure.parent_key == owner.key
    assert_coffee_call(repo, ("brewing/brewer.go", "brew", "accept(name)", "brewing/brewer.go", "brew.accept"))


class ResolutionAssertions(unittest.TestCase):
    def internal(self, repo, evidence, suffix):
        edges = call_edges(repo, evidence)
        self.assertTrue(edges, evidence)
        self.assertTrue(
            all(
                (
                    e.target_key.startswith("symbol:") and suffix in e.target_key
                    for e in edges
                )
            ),
            edges,
        )
        return edges

    def external(self, repo, evidence):
        edges = call_edges(repo, evidence)
        self.assertTrue(edges, evidence)
        self.assertTrue(
            all((e.target_key.startswith("external:") for e in edges)), edges
        )


class SemanticResolutionTest(ResolutionAssertions):
    def project(self, language, variant):
        from tests.import_project_support import project_sources, repository

        return repository(language, project_sources(language, variant))

    def unresolved(self, repo, case):
        language, path, owner, evidence, name = case
        return assert_coffee_call(repo, (
            path, owner, evidence, None, f"external:{language}:callable:{name}"
        ))

    def test_python_nonstatic_access_and_unknown_factory_results(self):
        repo = self.project("python", "semantic-orders")
        path = "src/coffee/orders/semantic.py"
        for owner, evidence, name in [
            ("class_receipt", "Brewer.brew(names)", "brew"),
            ("supplied_receipt", "unknown.brew(names)", "brew"),
            ("supplied_receipt", "factory().brew(names)", "brew"),
        ]:
            with self.subTest(evidence=evidence):
                self.unresolved(repo, ("python", path, owner, evidence, name))

    def test_python_import_shadowing_and_rebinding(self):
        repo = self.project("python", "semantic-orders")
        path = "src/coffee/orders/semantic.py"
        for owner in ("parameter", "unpacked", "rebound", "replaced_import"):
            with self.subTest(owner=owner):
                self.unresolved(repo, ("python", path, owner, "Drink.portions(name)", "portions"))
        assert_coffee_call(repo, (
            path, "local_recipe", "LocalDrink.portions(name)",
            "src/coffee/brewing/recipe.py", "Recipe.portions"
        ))
        self.unresolved(repo, ("python", path, "missing_recipe", "LocalDrink.portions(name)", "portions"))

    def test_python_conditional_bindings_do_not_select_house_recipe(self):
        repo = self.project("python", "lexical-orders")
        path = "src/coffee/orders/lexical.py"
        for owner in (
            "conditional", "loop", "with_stock", "exception", "future_assignment",
            "conditional_callable", "conditional_class",
        ):
            with self.subTest(owner=owner):
                self.unresolved(repo, ("python", path, owner, "Drink.portions(name)", "portions"))
        assert_coffee_call(repo, (
            path, "outside", "Drink.portions(name)",
            "src/coffee/brewing/recipe.py", "Recipe.portions"
        ))

    def test_receiver_rebinding_and_destructuring_preserve_ambiguity(self):
        for case in [
            ("python", "src/coffee/orders/reservations.py", ("redirect_inferred", "restore_batch")),
            ("javascript", "reservations/Intake.js", ("redirectInferred", "restoreBatch")),
            ("typescript", "reservations/Intake.ts", ("redirectInferred", "restoreBatch")),
        ]:
            self.assert_receiver_ambiguity(case)

    def assert_receiver_ambiguity(self, case):
        language, path, owners = case
        repo = self.project(language, "receiver-lifetime")
        for owner in owners:
            with self.subTest(language=language, owner=owner):
                self.unresolved(repo, (language, path, owner, "ledger.commit(order)", "commit"))

    def test_javascript_aliases_defaults_strings_and_unknown_factories(self):
        for language, extension in (("javascript", "js"), ("typescript", "ts")):
            self.assert_javascript_aliases(language, extension)

    def assert_javascript_aliases(self, language, extension):
        repo = self.project(language, "semantic-orders")
        path = f"ordering/SemanticOrders.{extension}"
        for evidence, target_path, target_name in [
            ("Drink.portions(name)", f"brewing/Recipe.{extension}", "Recipe.portions"),
            ("DefaultDrink.portions(name)", f"reporting/HouseRecipe.{extension}", "HouseRecipe.portions"),
        ]:
            with self.subTest(language=language, evidence=evidence):
                assert_coffee_call(repo, (path, "house", evidence, target_path, target_name))
        for owner, evidence, name in [
            ("replaceRecipe", "Drink.portions(name)", "portions"),
            ("parameterRecipe", "Drink.portions(name)", "portions"),
            ("unpackedRecipe", "Drink.portions(name)", "portions"),
            ("suppliedRecipe", "factory().portions(name)", "portions"),
            ("suppliedRecipe", "object.portions(name)", "portions"),
            ("unknownBrewer", "unknown.brew(names)", "brew"),
            ("unknownBrewer", "factory().brew(names)", "brew"),
        ]:
            with self.subTest(language=language, evidence=evidence):
                self.unresolved(repo, (language, path, owner, evidence, name))

    def test_typescript_type_only_and_conflicting_imports(self):
        repo = self.project("typescript", "semantic-orders")
        for name in ("TypedRecipeOrders", "TypedDefaultOrders", "ConflictingRecipes"):
            with self.subTest(module=name):
                self.unresolved(repo, ("typescript", f"ordering/{name}.ts", "portions", "Drink.portions(name)", "portions"))

    def test_javascript_callback_destructuring_shadows_only_callback(self):
        for language, extension in (("javascript", "js"), ("typescript", "ts")):
            self.assert_callback_shadowing(language, extension)

    def assert_callback_shadowing(self, language, extension):
        callbacks = {
            "single": "single.<anonymous>",
            "parenthesized": "parenthesized.<anonymous>",
            "objectParameter": "objectParameter.<anonymous>",
            "arrayParameter": "arrayParameter.<anonymous>",
            "nestedParameter": "nestedParameter.<anonymous>",
            "renamedParameter": "renamedParameter.<anonymous>",
        }
        repo = self.project(language, "lexical-orders")
        path = f"ordering/LexicalOrders.{extension}"
        for owner, callback in callbacks.items():
            with self.subTest(language=language, owner=owner):
                self.unresolved(repo, (language, path, callback, "Drink.portions(name)", "portions"))
                assert_coffee_call(repo, (
                    path, owner, "Drink.portions(name)", f"brewing/Recipe.{extension}", "Recipe.portions"
                ))

    def test_java_declared_packages_same_package_and_static_imports(self):
        repo = self.project("java", "semantic-orders")
        target_path = "physical/catalog/PortionSchedule.java"
        for path, owner, evidence in [
            ("physical/reporting/ReceiptOrders.java", "ReceiptOrders.total", "PortionSchedule.portions(name)"),
            ("physical/counter/TastingOrders.java", "TastingOrders.total", "PortionSchedule.portions(name)"),
            ("physical/counter/TastingOrders.java", "TastingOrders.total", "portions(name)"),
        ]:
            with self.subTest(path=path, evidence=evidence):
                assert_coffee_call(repo, (path, owner, evidence, target_path, "PortionSchedule.portions"))
        target, = coffee_symbols(repo, target_path, "PortionSchedule")
        imports = [edge for edge in resolve_connections(repo).connections
                   if edge.type == "IMPORTS" and edge.path == "physical/counter/TastingOrders.java"]
        method, = coffee_symbols(repo, target_path, "PortionSchedule.portions")
        self.assertEqual(len(imports), 2)
        self.assertEqual({edge.target_key for edge in imports}, {target.key, method.key})

    def test_java_wrong_namespace_and_duplicate_types_are_not_guessed(self):
        repo = self.project("java", "semantic-orders")
        self.unresolved(repo, ("java", "orders/WrongRecipeOrders.java", "WrongRecipeOrders.total", "Recipe.portions(name)", "portions"))
        self.unresolved(repo, ("java", "orders/SeasonalOrders.java", "SeasonalOrders.total", "SeasonalRecipe.portions(name)", "portions"))
        self.unresolved(repo, ("java", "orders/OverloadedOrders.java", "OverloadedOrders.total", "ReceiptRecipe.portions(name)", "portions"))
        imports = [edge for edge in resolve_connections(repo).connections
                   if edge.type == "IMPORTS" and edge.path == "orders/WrongRecipeOrders.java"]
        self.assertEqual(len(imports), 1)
        self.assertTrue(imports[0].target_key.startswith("external:"))
        wrong = self.project("java", "wrong-brewing-package")
        inherits = [edge for edge in resolve_connections(wrong).connections
                    if edge.type == "INHERITS" and edge.path == "orders/Tasting.java"]
        self.assertEqual(len(inherits), 1)
        self.assertTrue(inherits[0].target_key.startswith("external:"))

    def test_rust_declared_modules_and_path_relocations(self):
        repo = self.project("rust", "receipt-module-layout")
        for path, owner, evidence, target_path, target_name in [
            ("main.rs", "counter.close", "printer::render(names)", "receipt/print.rs", "render"),
            ("main.rs", "main", "crate::receipt::print::render(&names)", "receipt/print.rs", "render"),
            ("receipt.rs", "close", "custom::render(names)", "special/receipt_printer.rs", "render"),
            ("receipt.rs", "close", "seasonal::print::render(names)", "special/receipt_printer.rs", "render"),
            ("receipt.rs", "close", "alternate::print::render(names)", "receipt/alternate/print.rs", "render"),
            ("receipt.rs", "close", "daily::ledger::print::render(names)", "receipt/daily/ledger/print/mod.rs", "render"),
        ]:
            with self.subTest(evidence=evidence):
                assert_coffee_call(repo, (path, owner, evidence, target_path, target_name))
        self.unresolved(repo, ("rust", "main.rs", "main", "crate::print::render(&names)", "render"))
        self.unresolved(repo, ("rust", "main.rs", "main", "printer::render(&names)", "render"))

    def test_rust_duplicate_module_roots_are_ambiguous(self):
        repo = self.project("rust", "semantic-orders")
        self.unresolved(repo, ("rust", "src/main.rs", "main", "crate::receipt::render(&names)", "render"))

    def test_go_rebound_closure_keeps_owner_but_not_target(self):
        repo = self.project("go", "semantic-orders")
        path = "brewing/semantic_orders.go"
        owner, = coffee_symbols(repo, path, "seasonalOrders")
        closure, = coffee_symbols(repo, path, "seasonalOrders.accept")
        self.assertEqual(closure.parent_key, owner.key)
        self.unresolved(repo, ("go", path, "seasonalOrders", "accept(name)", "accept"))
