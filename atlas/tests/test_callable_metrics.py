"""Physical source spans and grammar-backed declared input counts."""

from shutil import copytree

import pytest
from atlas.bootstrap import repository_service
from atlas.indexer import analyze_repository
from atlas.persistence.database import migrate_database
from tests.coffee_consolidation import COFFEE_ROOT, coffee_parsed, coffee_symbols

@pytest.mark.parametrize(
    "case",
    [
        ("python", "src/coffee/orders/tracking.py", "track_delivery", [4], [3]),
        ("python", "src/coffee/orders/tracking.py", "track_events", [3], [2]),
        ("python", "src/coffee/orders/tracking.py", "PickupQueue.collect", [1], [4]),
        ("python", "src/coffee/orders/tracking.py", "PickupQueue.annotate", [1], [3]),
        ("javascript", "ordering/TrackingMetrics.js", "trackingQuote", [4], [3]),
        ("javascript", "ordering/TrackingMetrics.js", "trackingLabel", [1], [1]),
        ("javascript", "ordering/TrackingMetrics.js", "trackingQueue", [0], [1]),
        ("javascript", "ordering/TrackingMetrics.js", "PickupQueue.record", [2], [5]),
        ("typescript", "ordering/TrackingMetrics.ts", "trackingQuote", [3], [3]),
        ("go", "brewing/tracking.go", "Track", [3], [5]),
        ("go", "brewing/tracking.go", "TrackingFormat", [2], [3]),
        ("rust", "brewing/tracking.rs", "PickupQueue.record", [2], [7]),
        ("rust", "brewing/tracking.rs", "PickupQueue.take", [1], [4]),
        ("rust", "brewing/tracking.rs", "tracking_quote", [7], [5]),
        ("rust", "brewing/tracking.rs", "tracking_formatter", [0], [3]),
        ("rust", "brewing/tracking.rs", "tracking_formatter.<anonymous>", [2], [1]),
        ("kotlin", "orders/TrackingRates.kt", "track", [2], [4]),
        ("kotlin", "orders/TrackingRates.kt", "<anonymous>", [2, 0, None], [1, 1, 1]),
        ("elixir", "brewing/tracking.ex", "Coffee.Brewing.Tracking.quote", [2], [3]),
        ("elixir", "brewing/tracking.ex", "Coffee.Brewing.Tracking.empty", [0], [1]),
        ("elixir", "brewing/tracking.ex", "Coffee.Brewing.Tracking.labels.<anonymous>", [2, 0], [1, 1]),
    ],
)
def test_tracking_workflow_parameter_counts_and_spans(case):
    language, path, name, counts, lines = case
    file = coffee_parsed(language, path)
    symbols = coffee_symbols(file, name)
    assert [symbol.parameter_count for symbol in symbols] == counts
    assert [symbol.line_count for symbol in symbols] == lines


@pytest.mark.parametrize(
    "case",
    [
        ("python", "src/coffee/orders/service.py", "OrderService.place", [7], [10]),
        ("python", "src/coffee/orders/service.py", "audited.decorate.wrapped", [3], [3]),
        ("python", "src/coffee/orders/service.py", "OrderService.estimate", [3], [2]),
        ("python", "src/coffee/orders/service.py", "OrderService.stocked", [2], [4]),
        ("python", "src/coffee/orders/models.py", "OrderLine.espresso", [1], [2]),
        ("python", "src/coffee/orders/models.py", "Order.total", [0], [2]),
        ("python", "src/coffee/inventory/stock.py", "Inventory.receive", [2], [5]),
        ("python", "src/coffee/reporting/sales.py", "SalesReport.__init__.<anonymous>", [1], [1]),
        ("javascript", "ordering/Orders.js", "priceOrder", [3], [7]),
        ("javascript", "ordering/Orders.js", "createOrder", [3], [3]),
        ("javascript", "ordering/Orders.js", "drinkTickets.ticket", [2], [3]),
        ("typescript", "ordering/Orders.ts", "quoteWithFees", [3], [3]),
        ("typescript", "ordering/Orders.ts", "quote", [1, 2, 2], [1, 1, 5]),
        ("typescript", "ordering/Order.ts", "OrderBook.select", [1], [1]),
        ("typescript", "ordering/Order.ts", "OrderBook.onChange", [2], [1]),
        ("typescript", "inventory/Inventory.ts", "Inventory.constructor", [2], [1]),
        ("tsx", "CoffeeCard.tsx", "CoffeeCard", [1], [9]),
        ("tsx", "CoffeeCard.tsx", "CoffeeCard.<anonymous>", [0], [1]),
        ("tsx", "Basket.tsx", "Basket.total", [2], [4]),
        ("go", "recipe/recipe.go", "Scale", [3], [7]),
        ("go", "recipe/recipe.go", "Dose", [0], [3]),
        ("go", "brewing/inventory.go", "Restock.apply", [2], [4]),
        ("rust", "brewing/recipe.rs", "Recipe.label", [1], [3]),
        ("rust", "brewing/recipe.rs", "Recipe.scale", [1], [3]),
        ("rust", "brewing/recipe.rs", "Recipe.portions", [0], [3]),
        ("rust", "brewing/inventory.rs", "Inventory.new.<anonymous>", [1], [1]),
        ("java", "inventory/StockLedger.java", "StockLedger.snapshot", [1], [5]),
        ("java", "inventory/Inventory.java", "Inventory.receive", [1], [3]),
        ("java", "inventory/Inventory.java", "Inventory.reserve.<anonymous>", [1, 2], [2, 1]),
        ("java", "orders/Order.java", "Order.total", [0], [3]),
        ("java", "orders/OrderService.java", "OrderService.orders", [0], [3]),
        ("java", "orders/OrderService.java", "OrderService.place", [2, 4, 2], [3, 7, 4]),
        ("kotlin", "orders/Order.kt", "receipt", [1], [1]),
        ("kotlin", "inventory/Inventory.kt", "Inventory.receive", [1], [3]),
        ("kotlin", "inventory/Inventory.kt", "Inventory.reserve.<anonymous>", [1, 1], [1, 1]),
        ("kotlin", "reporting/SalesReport.kt", "SalesReport.projected.<anonymous>", [1, 1], [3, 1]),
        ("elixir", "brewing/recipe.ex", "Coffee.Brewing.Recipe.new", [2], [3]),
        ("elixir", "brewing/inventory.ex", "Coffee.Brewing.Inventory.restock", [3], [9]),
        ("elixir", "brewing/inventory.ex", "Coffee.Brewing.Inventory.restock.<anonymous>", [2], [7]),
        ("elixir", "brewing/brewer.ex", "Coffee.Brewing.Brewer.main", [0], [14]),
    ],
)
def test_coffee_parameter_counts_and_physical_spans(case):
    language, path, name, counts, lines = case
    file = coffee_parsed(language, path)
    symbols = coffee_symbols(file, name)
    assert [symbol.parameter_count for symbol in symbols] == counts
    assert [symbol.line_count for symbol in symbols] == lines
    assert all(symbol.kind in {"function", "method"} for symbol in symbols)


def test_python_receivers_only_in_methods():
    file = coffee_parsed("python", "src/coffee/orders/tracking.py")
    counts = {symbol.name: symbol.parameter_count for symbol in file.symbols
              if symbol.kind == "function"}
    assert counts == {
        "tracking_label": 2, "track_delivery": 4, "track_events": 3, "tracking_total": 2,
        "__init__": 0, "record": 1, "label": 2, "from_orders": 1,
        "notification": 2, "dispatch": 2, "collect": 1, "annotate": 1,
    }
    record = coffee_symbols(file, "PickupQueue.record")[0]
    nested = coffee_symbols(file, "PickupQueue.record.label")[0]
    assert nested.parent_key == record.key
    assert record.line_count == 5
    assert nested.line_count == 2


@pytest.mark.parametrize(("language", "path", "name"), [
    ("python", "src/coffee/orders/tracking.py", "tracking_total"),
    ("typescript", "ordering/TrackingMetrics.ts", "trackingTotal"),
])
def test_comments_separators_and_annotations_are_not_inputs(language, path, name):
    assert coffee_symbols(coffee_parsed(language, path), name)[0].parameter_count == 2


@pytest.mark.parametrize("name", ["brew", "retry"])
def test_elixir_clauses_keep_identity_and_counts(name):
    file = coffee_parsed("elixir", "brewing/brewer.ex")
    clauses = coffee_symbols(file, f"Coffee.Brewing.Brewer.{name}")
    assert [(symbol.name, symbol.parameter_count) for symbol in clauses] == [
        (name, 1), (name, 1),
    ]
    assert len({symbol.key for symbol in clauses}) == 2


def test_unknown_parameter_property_is_omitted():
    graph = analyze_repository(COFFEE_ROOT / "ruby")
    callable_node, = [node for node in graph.nodes
                      if node["path"] == "tracking.rb" and node["name"] == "record"]
    assert callable_node["properties"]["lineCount"] == 5
    assert "parameterCount" not in callable_node["properties"]


def test_metrics_survive_snapshot_persistence(tmp_path):
    root = tmp_path / "source"
    copytree(COFFEE_ROOT, root)
    path = tmp_path / "db.sqlite"
    migrate_database(path)
    with repository_service(path) as service:
        repository = service.register(
            {"name": "Callable metrics", "location": str(root)}
        )
        graph = service.index(repository.name, root)
    fresh = analyze_repository(root)
    expected = {node["stableKey"]: node["properties"] for node in fresh.nodes}
    with repository_service(path) as service:
        saved = service.get_architecture(repository.id)
        assert saved == graph
        facts = service.get_report_facts(repository.id)
        assert facts is not None
        for node in facts.nodes:
            assert node.lineCount == expected[node.stableKey].get("lineCount")
            assert node.parameterCount == expected[node.stableKey].get("parameterCount")
            assert node.cyclomaticComplexity == expected[node.stableKey].get("cyclomaticComplexity")
