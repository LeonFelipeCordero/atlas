"""Lexical lifetime contracts over complete coffee applications and order overlays."""

import pytest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.resolution_syntax import Syntax
from tests.test_semantic_resolution import call_edges, repository
from tests.variant_snapshot_support import VARIANT_ROOT, scenario_sources


def lexical_sources(language):
    return {
        source.path: source.source.decode()
        for source in scenario_sources(VARIANT_ROOT / language / "lexical-orders")
    }


def lexical_repository(language):
    return repository(language, lexical_sources(language))


def order_symbol_keys(repo, declaration):
    path, name = declaration
    keys = {s.key for s in repo.symbols if s.qualified_name == f"{path}::{name}"}
    assert keys, declaration
    return keys


def assert_order_spans(file, edges, evidence):
    lines = {e.line for e in edges}
    calls = [c for c in file.calls if c.evidence == evidence and c.line in lines]
    assert calls, evidence
    assert all(file.source.source[c.start_byte:c.end_byte].decode() == evidence for c in calls)
    assert len(edges) == len(calls), (evidence, edges)


def assert_order_target(repo, edges, target):
    if target is None:
        assert all(e.target_key.startswith("external:") for e in edges), edges
    else:
        assert {e.target_key for e in edges} == order_symbol_keys(repo, target), edges


def assert_order_call(repo, site, target=None):
    """Match declaration identities and unmodified original byte ranges."""
    path, owner, evidence = site
    file = next(file for file in repo.files if file.source.path == path)
    owners = order_symbol_keys(repo, (path, owner)) if owner is not None else {f"file:{path}"}
    edges = [e for e in call_edges(repo, evidence) if e.source_key in owners]
    assert_order_spans(file, edges, evidence)
    assert_order_target(repo, edges, target)
    return edges


PYTHON_PATH = "src/coffee/orders/lexical.py"
PYTHON_RECIPE = ("src/coffee/brewing/recipe.py", "Recipe.portions")


def test_python_blocks_bind_in_enclosing_function():
    repo = lexical_repository("python")
    for owner in ("conditional", "future_assignment", "loop", "with_stock", "exception",
                  "conditional_callable", "conditional_class"):
        assert_order_call(repo, (PYTHON_PATH, owner, "Drink.portions(name)"))
    assert_order_call(repo, (PYTHON_PATH, "outside", "Drink.portions(name)"), PYTHON_RECIPE)


def test_python_module_and_class_blocks_are_not_scopes():
    repo = lexical_repository("python")
    assert_order_call(repo, (PYTHON_PATH, "Menu", "MenuDrink.preview(name)"),
                      ("src/coffee/brewing/recipe.py", "Recipe.preview"))
    assert_order_call(repo, (PYTHON_PATH, "Menu.receipt", "MenuDrink.preview(name)"))
    assert_order_call(repo, (PYTHON_PATH, "Menu.portions", "Drink.portions(name)"), PYTHON_RECIPE)
    assert_order_call(repo, (PYTHON_PATH, None, "ConditionalDrink.portions(name)"), PYTHON_RECIPE)
    assert_order_call(repo, (PYTHON_PATH, "SeasonalMenu", "Drink.portions(name)"))
    assert_order_call(repo, (PYTHON_PATH, "SeasonalMenu.receipt", "Drink.preview(name)"),
                      ("src/coffee/brewing/recipe.py", "Recipe.preview"))
    assert_order_call(repo, (PYTHON_PATH, "SeasonalMenu.default_receipt", "Drink.preview(name)"))
    assert_order_call(repo, (PYTHON_PATH, "SeasonalMenu", "Drink.portions(drink_name)"), PYTHON_RECIPE)
    assert_order_call(repo, (PYTHON_PATH, "SeasonalMenu", "Drink.preview(name)"))
    assert_order_call(repo, ("src/coffee/orders/module_binding.py", None, "Drink.portions(name)"))


def test_python_conditional_import_order_and_scope():
    repo = lexical_repository("python")
    assert_order_call(repo, (PYTHON_PATH, "import_order", "Drink.portions(before)"))
    assert_order_call(repo, (PYTHON_PATH, "import_order", "Drink.portions(after)"))
    assert_order_call(repo, (PYTHON_PATH, "local_import", "LocalDrink.portions(name)"), PYTHON_RECIPE)
    assert_order_call(repo, (PYTHON_PATH, "missing_import", "LocalDrink.portions(name)"))
    file = next(f for f in repo.files if f.source.path == PYTHON_PATH)
    directive = next(i for i in file.imports if "LocalDrink" in file.source.source.decode().splitlines()[i.line - 1])
    scope = Syntax(file, get_resolution_adapter("python")).import_scope(directive.line)
    assert scope is not None and scope.type == "function_definition"


def test_python_class_import_cannot_be_captured_by_method():
    repo = lexical_repository("python")
    assert_order_call(repo, (PYTHON_PATH, "Receipt", "Drink.render(names)"),
                      ("src/coffee/reporting/report.py", "Report.render"))
    assert_order_call(repo, (PYTHON_PATH, "Receipt.portions", "Drink.portions(name)"))


def test_python_callback_and_comprehension_bindings():
    repo = lexical_repository("python")
    for owner in ("lambda_single", "lambda_default", "lambda_rest", "lambda_keyword", "lambda_keywords",
                  "list_orders", "generator_orders", "set_orders", "dict_orders", "nested_orders", "paired_orders", "filtered_orders"):
        callback_owner = owner + ".<anonymous>" if owner.startswith("lambda_") else owner
        assert_order_call(repo, (PYTHON_PATH, callback_owner, "Drink.portions(name)"))
        assert_order_call(repo, (PYTHON_PATH, owner, "Drink.preview(name)"),
                          ("src/coffee/brewing/recipe.py", "Recipe.preview"))
    assert_order_call(repo, (PYTHON_PATH, "first_iterable", "Drink.portions(name)"))
    assert_order_call(repo, (PYTHON_PATH, "first_iterable", "Drink.preview(name)"),
                      ("src/coffee/brewing/recipe.py", "Recipe.preview"))
    assert_order_call(repo, (PYTHON_PATH, "walrus_order", "Drink.portions(name)"))
    assert_order_call(repo, (PYTHON_PATH, "outside", "Drink.portions(name)"), PYTHON_RECIPE)


def test_python_parameter_shadows_callable_without_hiding_module_call():
    repo = lexical_repository("python")
    assert_order_call(repo, (PYTHON_PATH, "custom_receipt", "receipt(names)"))
    assert_order_call(repo, (PYTHON_PATH, "standard_receipt", "receipt(names)"), (PYTHON_PATH, "receipt"))


@pytest.mark.parametrize("language,extension", [("javascript", "js"), ("typescript", "ts")])
def test_javascript_and_typescript_callback_bindings(language, extension):
    repo = lexical_repository(language)
    path = f"ordering/LexicalOrders.{extension}"
    target = (f"brewing/Recipe.{extension}", "Recipe.portions")
    for owner in ("single", "parenthesized", "functionParameter", "namedFunction", "objectParameter",
                  "arrayParameter", "restParameter", "nestedParameter", "renamedParameter",
                  "defaultParameter", "restObject", "defaultObject", "selfNamed", "localCallable"):
        callback_owner = owner + {"namedFunction": ".inspect", "selfNamed": ".Drink"}.get(owner, ".<anonymous>")
        assert_order_call(repo, (path, callback_owner, "Drink.portions(name)"))
        assert_order_call(repo, (path, owner, "Drink.portions(name)"), target)
    for owner in ("propertyKey", "defaultValue"):
        assert_order_call(repo, (path, owner + ".<anonymous>", "Drink.portions(name)"), target)
        assert_order_call(repo, (path, owner, "Drink.portions(name)"), target)


def test_java_blocks_loops_catches_and_lambda_parameters():
    repo = lexical_repository("java")
    path = "orders/LexicalOrders.java"
    target = ("brewing/Recipe.java", "Recipe.portions")
    for owner in ("single", "parenthesized", "typed", "inferred", "multiple"):
        assert_order_call(repo, (path, f"LexicalOrders.{owner}.<anonymous>", "Recipe.portions(name)"))
        assert_order_call(repo, (path, f"LexicalOrders.{owner}", "Recipe.portions(name)"), target)
    for owner in ("block", "loop", "enhanced", "caught"):
        assert_order_call(repo, (path, f"LexicalOrders.{owner}", "Recipe.portions(local)"))
        assert_order_call(repo, (path, f"LexicalOrders.{owner}", "Recipe.portions(name)"), target)


def test_go_range_and_callback_bindings():
    repo = lexical_repository("go")
    path = "brewing/lexical_orders.go"
    target = ("recipe/recipe.go", "Portions")
    for owner in ("rangeOrders", "declaredOrders"):
        assert_order_call(repo, (path, owner, "Drink.Portions(local)"))
        assert_order_call(repo, (path, owner, "Drink.Portions(name)"), target)
    for owner in ("callbackOrders", "pairedCallbacks"):
        assert_order_call(repo, (path, owner + ".inspect", "Drink.Portions(name)"))
        assert_order_call(repo, (path, owner, "Drink.Portions(name)"), target)


def test_kotlin_lambda_and_range_bindings():
    repo = lexical_repository("kotlin")
    path = "orders/LexicalOrders.kt"
    target = ("brewing/Recipe.kt", "portions")
    for owner in ("single", "destructured", "loop", "pairedLoop", "nested"):
        callback_owner = {"loop": owner, "pairedLoop": owner, "nested": "nested.<anonymous>.<anonymous>"}.get(owner, owner + ".<anonymous>")
        assert_order_call(repo, (path, callback_owner, "dose(local)"))
        assert_order_call(repo, (path, owner, "dose(name)"), target)


def test_resolution_does_not_mutate_parsed_projects():
    from copy import deepcopy
    from atlas.metrics.resolver import resolve_connections

    for language in ("python", "javascript", "typescript", "java", "go", "kotlin", "rust"):
        repo = lexical_repository(language)
        original = deepcopy(repo)
        first = resolve_connections(repo)
        assert repo == original
        assert resolve_connections(repo) == first
        assert repo == original
