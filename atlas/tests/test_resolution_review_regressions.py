"""Review counterexamples use real coffee orders, imports, and receipt macros."""

import pytest

from atlas.metrics.resolver import resolve_connections
from tests.test_resolution_lexical_safety import (
    PYTHON_PATH, assert_order_call, lexical_repository, order_symbol_keys,
)
from tests.test_semantic_resolution import call_edges

RUST_PATH = "reporting/lexical_orders.rs"


def owner_calls(repo, path, owner):
    file = next(f for f in repo.files if f.source.path == path)
    symbol = next(s for s in file.symbols if s.qualified_name == f"{path}::{owner}")
    return [c for c in file.calls if symbol.start_byte <= c.start_byte < symbol.end_byte]


def assert_inherits(repo, derived, base):
    derived_key, = order_symbol_keys(repo, derived)
    base_key, = order_symbol_keys(repo, base)
    edges = [e for e in resolve_connections(repo).connections if e.type == "INHERITS" and e.source_key == derived_key]
    assert len(edges) == 1
    assert edges[0].target_key == base_key


def owner_call_names(repo, path, owner):
    return {c.name for c in owner_calls(repo, path, owner)}


def assert_no_nested_macro_targets(repo):
    targets = order_symbol_keys(repo, (RUST_PATH, "brew"))
    local_owners = {s.key for s in repo.symbols if s.file_path == RUST_PATH and s.name.startswith("nested_")}
    actual = {e.target_key for e in call_edges(repo) if e.source_key in local_owners}
    assert not actual.intersection(targets)


def test_java_base_is_looked_up_outside_derived_class_body():
    repo = lexical_repository("java")
    assert_inherits(repo, ("orders/LexicalOrders.java", "SeasonalBrewer"), ("brewing/Brewer.java", "Brewer"))


def test_python_future_class_body_bindings_do_not_shadow_base_header():
    repo = lexical_repository("python")
    for name in ("SeasonalRecipe", "ImportedRecipe"):
        assert_inherits(repo, (PYTHON_PATH, name), ("src/coffee/brewing/recipe.py", "Recipe"))


@pytest.mark.parametrize("language,extension", [("javascript", "js"), ("typescript", "ts")])
def test_namespace_default_and_named_exports_keep_real_keys_without_private_names(language, extension):
    repo = lexical_repository(language)
    path = f"ordering/ReceiptOrders.{extension}"
    target = (f"reporting/SeasonalReceipt.{extension}", "seasonalReceipt")
    for evidence in ("printReceipt(names)", "seasonal.default(names)", "seasonal.receipt(names)"):
        assert_order_call(repo, (path, "receipt", evidence), target)
    assert_order_call(repo, (path, "receipt", "seasonal.seasonalReceipt(names)"))


def test_stringification_unknown_and_overridden_macros_are_not_runtime_calls():
    repo = lexical_repository("rust")
    for owner in ("source_labels", "nested_custom_definition", "aliased_standard_namespace"):
        assert "brew" not in owner_call_names(repo, RUST_PATH, owner)
    custom_names = owner_call_names(repo, "reporting/custom_lexical_orders.rs", "source_label")
    assert "brew" not in custom_names
    assert owner_call_names(repo, RUST_PATH, "source_labels") == {"println!", "stringify!", "custom!"}
    assert "println!" in custom_names
    assert "dbg!" in owner_call_names(repo, RUST_PATH, "nested_custom_definition")
    assert "std::dbg!" in owner_call_names(repo, RUST_PATH, "aliased_standard_namespace")


def test_macro_local_and_nested_bindings_do_not_become_repository_functions():
    repo = lexical_repository("rust")
    for owner in ("local_binding", "nested_binding", "nested_mutable_binding", "nested_function", "nested_callback"):
        edges = assert_order_call(repo, (RUST_PATH, owner, "brew(names)"))
        assert len(edges) == 1
    assert_no_nested_macro_targets(repo)


def test_rust_closure_parameter_shadows_bare_function_only_in_callback():
    repo = lexical_repository("rust")
    assert_order_call(repo, (RUST_PATH, "closure_parameter.<anonymous>", "brew(names)"))
    assert_order_call(repo, (RUST_PATH, "closure_parameter", "brew(names)"), (RUST_PATH, "brew"))


def test_macro_method_receivers_do_not_become_module_namespaces():
    repo = lexical_repository("rust")
    assert_order_call(repo, (RUST_PATH, "method_receiver", "recipe.portions(name)"))
