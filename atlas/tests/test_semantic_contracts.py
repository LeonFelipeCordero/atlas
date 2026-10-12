"""End-to-end extraction contracts over whole coffee application dictionaries."""

import pytest

from tests.test_resolution_lexical_safety import PYTHON_PATH, assert_order_call, lexical_repository
from tests.test_resolution_review_regressions import RUST_PATH
from tests.test_semantic_resolution import call_edges


def test_macro_inner_calls_have_original_utf8_source_spans_and_hints():
    repo = lexical_repository("rust")
    file = next(f for f in repo.files if f.source.path == RUST_PATH)
    symbol = next(s for s in file.symbols if s.qualified_name == f"{RUST_PATH}::original_span")
    calls = [c for c in file.calls if c.name == "brew" and symbol.start_byte <= c.start_byte < symbol.end_byte]
    assert len(calls) == 1
    call = calls[0]
    assert call.start_byte == file.source.source.index(b"brew(names)", symbol.start_byte)
    assert call.end_byte == call.start_byte + len(b"brew(names)")
    assert file.source.source[call.start_byte:call.end_byte] == b"brew(names)"
    assert call.evidence == "brew(names)"
    assert call.bare_target
    assert call.qualifier is None
    assert_order_call(repo, (RUST_PATH, "original_span", "brew(names)"), (RUST_PATH, "brew"))


@pytest.mark.parametrize("case", [
    ("python", PYTHON_PATH, "unlinked", "Brewer()", "Brewer().brew(names)"),
    ("typescript", "ordering/ReceiptOrders.ts", "unlinked", "new Brewer()", "new Brewer().brew(names)"),
])
def test_constructor_identity_never_uses_global_type_guessing(case):
    language, path, owner, constructor, evidence = case
    repo = lexical_repository(language)
    assert any(s.name == "Brewer" and s.kind == "class" for s in repo.symbols)
    assert_order_call(repo, (path, owner, constructor))
    assert_order_call(repo, (path, owner, evidence))


def test_java_static_member_import_retains_recipe_identity():
    repo = lexical_repository("java")
    assert_order_call(repo, ("inventory/Inventory.java", "Inventory.reserve", "portions(line.drink)"),
                      ("brewing/Recipe.java", "Recipe.portions"))


def is_retry_clause(symbol, path):
    return (symbol.qualified_name == f"{path}::Coffee.Brewing.RetryOrders.retry"
            and symbol.signature is not None and "retry(names, attempts)" in symbol.signature)


def retry_candidates(repo, path):
    return [s for s in repo.symbols if is_retry_clause(s, path)]


def assert_other_retry_targets_excluded(repo, candidates, edges):
    excluded = {s.key for s in repo.symbols if "RetryOrders.retry" in s.qualified_name and s not in candidates}
    assert excluded
    assert not excluded.intersection(e.target_key for e in edges)


def test_elixir_clause_arity_and_unrelated_modules_remain_ambiguous():
    repo = lexical_repository("elixir")
    path = "brewing/retry_orders.ex"
    edges = [e for e in call_edges(repo, "retry(names, attempts - 1)") if path in e.source_key]
    candidates = retry_candidates(repo, path)
    assert len(candidates) == len(edges) == 2
    assert {e.target_key for e in edges} == {s.key for s in candidates}
    assert_other_retry_targets_excluded(repo, candidates, edges)


def test_rust_object_dot_is_not_a_module_reference():
    repo = lexical_repository("rust")
    assert_order_call(repo, (RUST_PATH, "method_receiver", "recipe.portions(name)"))


def test_receiver_rebinding_and_prototype_replacement():
    repo = lexical_repository("python")
    assert_order_call(repo, (PYTHON_PATH, "RetryOrders.retry", "self.retry(names, attempts - 1, replacement)"))
    repo = lexical_repository("typescript")
    for owner in ("replacedPrototype", "replacedMethod"):
        assert_order_call(repo, ("ordering/ReceiptOrders.ts", owner, "new ReceiptPrinter().render(names)"))
