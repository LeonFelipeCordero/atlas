"""Source-grounded coffee resolution and isolated ambiguity/grammar regressions."""

from tests.resolution_snapshot_support import fixture_sources
import unittest
from pathlib import Path

import pytest

from tests.coffee_fixture import FIXTURE_ROOT
from atlas.parsing.discovery import SourceFile, discover_files
from atlas.parsing.parser import parse_files
from atlas.metrics.resolver import resolve_connections


def repository(language, sources):
    return parse_files(
        [
            SourceFile(path, Path("/semantic") / path, language, source.encode())
            for path, source in sources.items()
        ]
    )


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
    def test_python_dotted_module_import_and_nonstatic_member(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_python_dotted_module_import_and_nonstatic_member:62-15"
            ),
        )
        # Coffee covers dotted imports; this fixture isolates nonstatic class access.
        self.external(repo, "Recipe.instance()")

    def test_python_self_and_immediate_construction_are_precise(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_python_self_and_immediate_construction_are_precise:73-15"
            ),
        )
        # Positive construction/recursion moved to coffee; unknown results stay isolated.
        self.external(repo, "unknown.brew()")
        self.external(repo, "factory().brew()")

    def test_import_shadowing_and_rebinding_never_guess(self):
        usages = [
            "import-shadowing-and-rebinding-never-guess-python-01",
            "import-shadowing-and-rebinding-never-guess-python-02",
            "import-shadowing-and-rebinding-never-guess-python-03",
            "import-shadowing-and-rebinding-never-guess-python-04",
            "import-shadowing-and-rebinding-never-guess-python-05",
            "import-shadowing-and-rebinding-never-guess-python-06",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "python",
                    fixture_sources(
                        "semantic_resolution:test_import_shadowing_and_rebinding_never_guess:105-23",
                        usage=usage,
                    ),
                )
                self.external(repo, "R.portions(1)")

    def test_nested_import_does_not_leak_and_strings_are_not_writes(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_nested_import_does_not_leak_and_strings_are_not_writes:115-15"
            ),
        )
        assert_coffee_call(repo, ("main.py", "inside", "R.portions(1)", "recipe.py", "Recipe.portions"))
        self.external(repo, "R.portions(2)")
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_resolution:test_nested_import_does_not_leak_and_strings_are_not_writes:124-15"
            ),
        )
        assert_coffee_call(repo, ("main.ts", None, "R.portions(1)", "recipe.ts", "Recipe.portions"))

    def test_javascript_imported_classes_static_recursion_and_new_receiver(self):
        for language, extension in [("javascript", "js"), ("typescript", "ts")]:
            with self.subTest(language=language):
                repo = repository(
                    language,
                    fixture_sources(
                        "semantic_resolution:test_javascript_imported_classes_static_recursion_and_new_receiver:136-23",
                        language=language,
                    ),
                )
                # Recursion/new moved to coffee, but aliased static class imports
                # are absent from these JS/TS coffee projects; keep exact coverage.
                assert_coffee_call(repo, (f"main.{extension}", "Maker.brew", "R.portions(1)", f"recipe.{extension}", "Recipe.portions"))
                self.external(repo, "unknown.brew()")

    def test_javascript_default_exports_and_type_only_imports(self):
        # Coffee uses named exports, so retain the differently-named default class.
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_resolution:test_javascript_default_exports_and_type_only_imports:152-15"
            ),
        )
        assert_coffee_call(repo, ("main.ts", None, "R.portions(1)", "recipe.ts", "Actual.portions"))
        for imported in [
            "javascript-default-exports-and-type-only-imports-typescript-02",
            "javascript-default-exports-and-type-only-imports-typescript-03",
        ]:
            repo = repository(
                "typescript",
                fixture_sources(
                    "semantic_resolution:test_javascript_default_exports_and_type_only_imports:164-19",
                    imported=imported,
                ),
            )
            self.external(repo, "R.portions(1)")

    def test_javascript_parameter_destructuring_rebind_and_duplicates(self):
        usages = [
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-01",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-02",
            "R = other; R.portions(1);",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-04",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-05",
            "factory().portions(1);",
            "object.portions(1);",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "typescript",
                    fixture_sources(
                        "semantic_resolution:test_javascript_parameter_destructuring_rebind_and_duplicates:185-23",
                        usage=usage,
                    ),
                )
                evidence = (
                    "factory().portions(1)"
                    if usage.startswith("factory")
                    else "object.portions(1)"
                    if usage.startswith("object")
                    else "R.portions(1)"
                )
                self.external(repo, evidence)

    def test_java_declared_packages_and_same_package_types(self):
        # Deliberately mismatched directory/package layout is absent from coffee.
        repo = repository(
            "java",
            fixture_sources(
                "semantic_resolution:test_java_declared_packages_and_same_package_types:203-15"
            ),
        )
        assert_coffee_call(repo, ("physical/Report.java", "Report.total", "Recipe.portions(2)", "odd/Recipe.java", "Recipe.portions"))
        assert_coffee_call(repo, ("elsewhere/App.java", "App.run", "Recipe.portions(1)", "odd/Recipe.java", "Recipe.portions"))
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertEqual(len(imports), 1)
        target, = coffee_symbols(repo, "odd/Recipe.java", "Recipe")
        self.assertEqual(imports[0].target_key, target.key)

    def test_declared_import_identity_not_terminal_name(self):
        repo = repository(
            "java",
            fixture_sources(
                "semantic_resolution:test_declared_import_identity_not_terminal_name:220-15"
            ),
        )
        self.external(repo, "Recipe.portions()")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(imports[0].target_key.startswith("external:"))

    def test_rust_path_modules_and_crate_imports(self):
        # Explicit #[path] relocation is a layout probe, not coffee's mod.rs tree.
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_resolution:test_rust_path_modules_and_crate_imports:254-15"
            ),
        )
        assert_coffee_call(repo, ("src/main.rs", "main", "recipe::portions(1)", "odd/recipe.rs", "portions"))
        assert_coffee_call(repo, ("odd/recipe.rs", "preview", "report::render()", "view/report.rs", "render"))
        assert_coffee_call(repo, ("view/report.rs", "render", "crate::recipe::portions(2)", "odd/recipe.rs", "portions"))
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertEqual(len(imports), 4)
        self.assertEqual({(e.source_key, e.target_key) for e in imports}, {
            ("file:src/main.rs", "file:odd/recipe.rs"),
            ("file:src/main.rs", "file:view/report.rs"),
            ("file:odd/recipe.rs", "file:view/report.rs"),
            ("file:view/report.rs", "file:odd/recipe.rs"),
        })

    def test_rust_duplicate_module_roots_are_ambiguous(self):
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_resolution:test_rust_duplicate_module_roots_are_ambiguous:272-15"
            ),
        )
        self.external(repo, "crate::tools::work()")

    def test_named_go_closure_and_rebinding(self):
        # The normal bound closure is coffee's brew.accept; retain only mutation.
        self.check_go_closure(True)

    def check_go_closure(self, rebind):
        repo = repository(
            "go",
            fixture_sources(
                "semantic_resolution:check_go_closure:301-15", rebind=rebind
            ),
        )
        file = repo.files[0]
        owner = next((s for s in file.symbols if s.name == "brew"))
        closure = next((s for s in file.symbols if s.name == "accept"))
        self.assertEqual(closure.parent_key, owner.key)
        self.external(repo, "accept(1)")

    def test_ambiguous_types_and_methods_do_not_choose_first(self):
        repo = repository(
            "java",
            fixture_sources(
                "semantic_resolution:test_ambiguous_types_and_methods_do_not_choose_first:319-15"
            ),
        )
        self.external(repo, "R.work()")
