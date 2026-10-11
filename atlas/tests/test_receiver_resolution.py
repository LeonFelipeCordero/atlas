"""Whole-project receiver identities; isolated unknown/mutated receiver probes."""

import pytest

from tests.resolution_snapshot_support import fixture_sources
from tests.test_semantic_resolution import (
    assert_coffee_call,
    call_edges,
    coffee_repository,
    coffee_symbols,
    repository,
)

CASES = ("java", "kotlin", "typescript", "tsx", "python", "go", "rust", "javascript")

# Each tuple identifies a real caller and the exact declaration it must reach.
RECEIVER_CALLS = [
    ("python", "src/coffee/orders/service.py", "OrderService.fulfill", "self.inventory.reserve(order)", "src/coffee/inventory/stock.py", "Inventory.reserve"),
    ("python", "src/coffee/orders/service.py", "OrderService.fulfill", "self.brewer.brew(order.names())", "src/coffee/brewing/brewer.py", "Brewer.brew"),
    ("python", "src/coffee/orders/service.py", "OrderService.preview", "brewer.brew(order.names())", "src/coffee/brewing/brewer.py", "Brewer.brew"),
    ("python", "src/coffee/orders/service.py", "OrderService.stocked", "stock.receive(espresso=espresso, filter=filter)", "src/coffee/inventory/stock.py", "Inventory.receive"),
    ("java", "orders/OrderService.java", "OrderService.fulfill", "inventory.reserve(order)", "inventory/Inventory.java", "Inventory.reserve"),
    ("java", "orders/OrderService.java", "OrderService.fulfill", "brewer.brew(order.names())", "brewing/Brewer.java", "Brewer.brew"),
    ("java", "orders/OrderService.java", "OrderService.preview", "station.brew(order.names())", "brewing/Brewer.java", "Brewer.brew"),
    ("java", "orders/OrderService.java", "OrderService.stocked", 'inventory.receive(new Change("espresso", espresso, "opening"),\n                          new Change("filter", filter, "opening"))', "inventory/Inventory.java", "Inventory.receive"),
    ("kotlin", "orders/OrderService.kt", "OrderService.fulfill", "brewer.brew(order.names())", "brewing/Brewer.kt", "Brewer.brew"),
    ("kotlin", "orders/OrderService.kt", "OrderService.preview", "station.brew(order.names())", "brewing/Brewer.kt", "Brewer.brew"),
    ("kotlin", "inventory/Inventory.kt", "Inventory.Companion.stocked", 'inventory.receive(Change("espresso", espresso, "opening"), Change("filter", filter, "opening"))', "inventory/Inventory.kt", "Inventory.receive"),
    ("typescript", "ordering/OrderService.ts", "OrderService.fulfill", "this.inventory.reserve(order)", "inventory/Inventory.ts", "Inventory.reserve"),
    ("typescript", "ordering/OrderService.ts", "OrderService.fulfill", "this.brewer.brew(names)", "brewing/Brewer.ts", "Brewer.brew"),
    ("typescript", "ordering/OrderService.ts", "OrderService.fulfill", "this.receipt.render(order)", "reporting/Receipt.ts", "Receipt.render"),
    ("typescript", "ordering/OrderService.ts", "OrderService.describe.<anonymous>", "this.recipe.describe(name)", "brewing/Recipe.ts", "Recipe.describe"),
    ("typescript", "ordering/OrderService.ts", "checkStock", "inventory.canFill(order)", "inventory/Inventory.ts", "Inventory.canFill"),
    ("typescript", "ordering/OrderService.ts", "morningOrder", "inventory.restock({ beans: 250 })", "inventory/Inventory.ts", "Inventory.restock"),
    ("javascript", "ordering/OrderService.js", "morningOrder", "inventory.restock({ beans: 250 })", "inventory/Inventory.js", "Inventory.restock"),
    ("javascript", "ordering/OrderService.js", "OrderService.describe.<anonymous>", "this.recipe.describe(name)", "brewing/Recipe.js", "Recipe.describe"),
    ("tsx", "Basket.tsx", "startOrder", "basket.add(name, quantity)", "Basket.tsx", "Basket.add"),
    ("tsx", "Basket.tsx", "orderTotal", "basket.total(discount)", "Basket.tsx", "Basket.total"),
    ("go", "brewing/brewer.go", "Brew", "b.stock.Reserve(name)", "brewing/inventory.go", "Reserve"),
    ("go", "brewing/order.go", "Serve", "brewer.Brew(o.Names)", "brewing/brewer.go", "Brew"),
    ("go", "brewing/brewer.go", "Main", 'stock.Remaining("filter")', "brewing/inventory.go", "Remaining"),
    ("rust", "brewing/brewer.rs", "Brewer.brew", "self.stock.reserve(name)", "brewing/inventory.rs", "Inventory.reserve"),
    ("rust", "main.rs", "main", "maker.brew(&names)", "brewing/brewer.rs", "Brewer.brew"),
    ("rust", "reporting/report.rs", "Report.estimate", "drink.portions()", "brewing/recipe.rs", "Recipe.portions"),
]


@pytest.mark.parametrize("case", RECEIVER_CALLS)
def test_coffee_declared_receivers(case):
    language, *call = case
    assert_coffee_call(coffee_repository(language), call)


# Deliberately exact limitations, not an internal-or-external escape hatch.
UNRESOLVED_RECEIVERS = [
    ("javascript", "ordering/OrderService.js", "OrderService.fulfill", "this.inventory.reserve(order)", "reserve", "Default constructor arguments do not type unannotated injected fields."),
    ("javascript", "ordering/OrderService.js", "OrderService.fulfill", "this.brewer.brew(names)", "brew", "Unannotated injected fields have no declared receiver type."),
    ("javascript", "ordering/OrderService.js", "OrderService.fulfill", "this.receipt.render(order)", "render", "Unannotated injected fields have no declared receiver type."),
    ("kotlin", "orders/OrderService.kt", "OrderService.fulfill", "inventory.reserve(order)", "reserve", "Inventory primary field with a same-named secondary constructor parameter remains unresolved; Brewer field resolves."),
    ("tsx", "App.tsx", "Menu.addDrink", "basket.add(name, quantity)", "add", "Basket type nested in destructured prop is not a direct receiver binding."),
]


@pytest.mark.parametrize("case", UNRESOLVED_RECEIVERS)
def test_coffee_receiver_limits_are_explicit(case):
    language, path, owner, evidence, name, reason = case
    assert reason
    assert_coffee_call(coffee_repository(language), (path, owner, evidence, None, f"external:{language}:callable:{name}"))


@pytest.mark.parametrize("language", ("go", "rust"))
def test_declared_receiver_forms_absent_from_coffee(language):
    # Go's uninitialized pointer local and Rust's borrowed parameter/struct literal
    # are not coffee's constructor-returned locals. Keep their exact old inputs.
    repo = repository(language, fixture_sources("receiver_resolution:test_declared_receivers:24-11", language=language))
    path = "app.go" if language == "go" else "app.rs"
    name = "persist" if language == "go" else "Service.persist"
    target, = coffee_symbols(repo, path, name)
    for evidence in ("parameter.persist()", "local.persist()"):
        edges = call_edges(repo, evidence)
        assert len(edges) == 1
        assert edges[0].target_key == target.key


@pytest.mark.parametrize("language", CASES)
def test_unknown_receiver_never_uses_member_name(language):
    repo = repository(
        language,
        fixture_sources(
            "receiver_resolution:test_unknown_receiver_never_uses_member_name:34-11",
            language=language,
        ),
    )
    edges = call_edges(repo, "unknown.persist()")
    assert edges
    assert all(e.target_key.startswith("external:") for e in edges)


@pytest.mark.parametrize("language", ("python", "javascript", "typescript"))
def test_reassigned_inferred_receiver_stays_external(language):
    edges = call_edges(
        repository(
            language,
            fixture_sources(
                "receiver_resolution:test_reassigned_inferred_receiver_stays_external:46-23",
                language=language,
            ),
        ),
        "local.persist()",
    )
    assert edges and all(e.target_key.startswith("external:") for e in edges)


def test_elixir_has_module_calls_not_instance_members():
    # Coffee exercises module calls; dynamic lowercase receiver stays isolated.
    repo = repository(
        "elixir",
        fixture_sources("receiver_resolution:test_elixir_has_module_calls_not_instance_members:51-11"),
    )
    dynamic = call_edges(repo, "service.persist()")
    assert dynamic and all(e.target_key.startswith("external:") for e in dynamic)
