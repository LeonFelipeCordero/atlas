"""Binding guards on whole coffee projects and member-collision overlays."""

import pytest

from atlas.metrics.adapters.resolution import _namespace_binding
from tests.coffee_fixture import coffee_sources
from tests.import_project_support import (
    assert_call,
    assert_external,
    project_repository,
    project_sources,
    repository,
    symbols,
)


@pytest.mark.parametrize("case", [
    ("python", "selective-recipe", "src/coffee/brewing/tasting.py", "from coffee.brewing.recipe import portions"),
    ("typescript", "selective-roast", "brewing/preview.ts", 'import { reserve } from "../inventory/roast.ts";'),
])
def test_selective_imports_never_bind_module_namespace(case):
    language, variant, path, evidence = case
    repo = project_repository(language, variant)
    source = next(file.source.source.decode() for file in repo.files if file.source.path == path)
    assert evidence in source
    assert _namespace_binding(evidence, "recipe" if language == "python" else "roast") is None
    if language == "python":
        assert_call(repo, (path, 'portions("espresso")'), ("src/coffee/brewing/recipe.py", "portions"))
        assert_external(repo, path, 'recipe.portions("espresso")')
    else:
        assert_call(repo, (path, 'reserve("espresso")'), ("inventory/roast.ts", "reserve"))
        assert_external(repo, path, 'roast.reserve("espresso")')


@pytest.mark.parametrize(
    "case",
    [
        (
            "python", "src/coffee/orders/reservations.py", "reserve", "reserve(order)",
            "supplier.reserve(order)", "src/coffee/inventory/delivery.py", "delivery_label",
            "delivery_label(order)", "supplier.delivery_label(order)",
        ),
        (
            "typescript", "ordering/Reservations.ts", "reserve", "reserve(order)",
            "supplier.reserve(order)", "inventory/Delivery.ts", "deliveryLabel",
            "deliveryLabel(order)", "supplier.deliveryLabel(order)",
        ),
        (
            "java", "orders/Reservations.java", "Reservations.reserve", "reserve(order)",
            "supplier.reserve(order)", "inventory/Delivery.java", "Delivery.deliveryLabel",
            "deliveryLabel(order)", "supplier.deliveryLabel(order)",
        ),
        (
            "kotlin", "orders/Reservations.kt", "reserve", "reserve(order)",
            "supplier.reserve(order)", "inventory/Delivery.kt", "deliveryLabel",
            "deliveryLabel(it)", "supplier.deliveryLabel(order)",
        ),
        (
            "go", "brewing/reservations.go", "Reserve", "Reserve(order)",
            "supplier.Reserve(order)", "reporting/delivery.go", "DeliveryLabel",
            "DeliveryLabel(order)", "supplier.DeliveryLabel(order)",
        ),
        (
            "rust", "brewing/reservations.rs", "reserve", "reserve(names, customer)",
            "supplier.reserve(names)", "brewing/delivery.rs", "delivery_label",
            "delivery_label(names, customer)", "supplier.delivery_label(names, customer)",
        ),
        (
            "csharp", "orders/Reservations.cs", "Reservations.Reserve", "Reserve(customer, drink, units)",
            "supplier.Reserve(drink, units)", "inventory/Delivery.cs", "Delivery.DeliveryLabel",
            "DeliveryLabel(customer, drink.Key, drink.Value)", "supplier.DeliveryLabel(customer, drink, units)",
        ),
        (
            "ruby", "orders/reservations.rb", "reserve", "reserve(customer, drink, units)",
            "supplier.reserve(drink, units)", "inventory/delivery.rb", "delivery_label",
            "delivery_label(customer, drink, units)", "supplier.delivery_label(customer, drink, units)",
        ),
    ],
)
def test_member_calls_do_not_borrow_local_or_project_declarations(case):
    (language, path, local_symbol, local_call, member_call,
     delivery_path, delivery_symbol, delivery_call, member_delivery) = case
    repo = project_repository(language, "member-collision")
    assert all(file.source.language == language and file.parse_error is None for file in repo.files)
    merged = {file.source.path: file.source.source for file in repo.files}
    for source in coffee_sources(language):
        if source.language not in {"gomod", "toml"}:
            assert merged[source.path].startswith(source.source)

    assert_call(repo, (path, local_call), (path, local_symbol))
    assert_external(repo, path, member_call)

    # A unique project-wide name is a tempting but invalid member-call fallback.
    delivery = symbols(repo, delivery_path, delivery_symbol)
    assert [symbol for symbol in repo.symbols if symbol.name == delivery[0].name] == delivery
    assert_call(repo, (delivery_path, delivery_call), (delivery_path, delivery_symbol))
    assert_external(repo, path, member_delivery)


@pytest.mark.parametrize("case", [
    ("python", "src/coffee/orders/reservations.py", "inventory.reserve(order)",
     "src/coffee/inventory/stock.py", "Inventory.reserve"),
    ("typescript", "ordering/Reservations.ts", "inventory.reserve(order)",
     "inventory/Inventory.ts", "Inventory.reserve"),
    ("java", "orders/Reservations.java", "inventory.reserve(order)",
     "inventory/Inventory.java", "Inventory.reserve"),
    ("kotlin", "orders/Reservations.kt", "inventory.reserve(order)",
     "inventory/Inventory.kt", "Inventory.reserve"),
    ("go", "brewing/reservations.go", "inventory.Reserve(name)",
     "brewing/inventory.go", "Reserve"),
    ("rust", "brewing/brewer.rs", "self.stock.reserve(name)",
     "brewing/inventory.rs", "Inventory.reserve"),
])
def test_member_collision_keeps_real_inventory_binding(case):
    language, path, evidence, target_path, target_name = case
    assert_call(project_repository(language, "member-collision"), (path, evidence), (target_path, target_name))


def test_project_repository_uses_each_files_grammar_and_skips_manifests():
    languages = ("python", "typescript", "java", "kotlin", "go", "rust", "csharp", "ruby", "tsx")
    sources = {
        f"{language}/{path}": text
        for language in languages
        for path, text in project_sources(language).items()
    }
    assert "go/go.mod" in sources and "rust/Cargo.toml" in sources
    repo = repository("python", sources)
    assert {file.source.language for file in repo.files} == set(languages)
    assert all(file.source.language == file.source.path.split("/")[0] for file in repo.files)
    assert {file.source.path for file in repo.files} == set(sources) - {"go/go.mod", "rust/Cargo.toml"}
