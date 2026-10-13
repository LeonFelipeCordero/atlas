"""Whole coffee projects and coherent order receiver-lifetime overlays."""

import pytest

from tests.test_receiver_safety import assert_lifetime_call
from tests.test_semantic_resolution import (
    assert_coffee_call,
    coffee_repository,
)

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
    ("kotlin", "orders/OrderService.kt", "OrderService.fulfill", "inventory.reserve(order)", "inventory/Inventory.kt", "Inventory.reserve"),
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
    ("rust", "main.rs", "main", 'Inventory::new(&[("espresso", 12), ("filter", 9)])', "brewing/inventory.rs", "Inventory.new"),
    ("rust", "main.rs", "main", "Brewer::new(stock)", "brewing/brewer.rs", "Brewer.new"),
    ("rust", "main.rs", "main", 'Recipe::new("filter", 1)', "brewing/recipe.rs", "Recipe.new"),
    ("rust", "reporting/mod.rs", "daily.close", "Receipt::new(names)", "reporting/report.rs", "Report.new"),
    ("rust", "reporting/report.rs", "Report.estimate", 'Drink::new("filter", cups)', "brewing/recipe.rs", "Recipe.new"),
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
    ("tsx", "App.tsx", "Menu.addDrink", "basket.add(name, quantity)", "add", "Basket type nested in destructured prop is not a direct receiver binding."),
]


@pytest.mark.parametrize("case", UNRESOLVED_RECEIVERS)
def test_coffee_receiver_limits_are_explicit(case):
    language, path, owner, evidence, name, reason = case
    assert reason
    assert_coffee_call(coffee_repository(language), (path, owner, evidence, None, f"external:{language}:callable:{name}"))


@pytest.mark.parametrize("language", ("go", "rust"))
def test_declared_receiver_forms_absent_from_coffee(language):
    path = "reservations/ledger.go" if language == "go" else "reservation_intake.rs"
    owner = "Receive" if language == "go" else "receive"
    method = "Commit" if language == "go" else "commit"
    target = "Commit" if language == "go" else "ReservationLedger.commit"
    for receiver in ("parameter", "local"):
        assert_lifetime_call(language, (path, owner, f"{receiver}.{method}(order)"), (path, target))


UNKNOWN_WORKFLOWS = [
    ("python", "src/coffee/orders/reservations.py", "accept_unknown"),
    ("java", "intake/ReservationIntake.java", "ReservationIntake.unknown"),
    ("kotlin", "intake/ReservationIntake.kt", "receiveUnknown"),
    ("go", "reservations/ledger.go", "ReceiveUnknown"),
    ("rust", "reservation_intake.rs", "receive_unknown"),
    ("javascript", "reservations/Intake.js", "acceptUnknown"),
    ("typescript", "reservations/Intake.ts", "acceptUnknown"),
    ("tsx", "reservations/Intake.tsx", "acceptUnknown"),
]


@pytest.mark.parametrize("language,path,owner", UNKNOWN_WORKFLOWS)
def test_unknown_receiver_never_uses_member_name(language, path, owner):
    method = "Commit" if language == "go" else "commit"
    assert_lifetime_call(language, (path, owner, f"unknown.{method}(order)"))


@pytest.mark.parametrize("language,path,owner", [
    ("python", "src/coffee/orders/reservations.py", "redirect_inferred"),
    ("javascript", "reservations/Intake.js", "redirectInferred"),
    ("typescript", "reservations/Intake.ts", "redirectInferred"),
    ("tsx", "reservations/Intake.tsx", "redirectInferred"),
])
def test_reassigned_inferred_receiver_stays_external(language, path, owner):
    assert_lifetime_call(language, (path, owner, "ledger.commit(order)"))


def test_elixir_has_module_calls_not_instance_members():
    path = "reservations/intake.ex"
    owner = "Coffee.Reservations.Intake.fulfill"
    assert_lifetime_call("elixir", (path, owner, "Ledger.commit(order)"),
                         (path, "Coffee.Reservations.Ledger.commit"))
    assert_lifetime_call("elixir", (path, owner, "ledger.commit(order)"))
