"""Physical source spans and grammar-backed declared input counts."""

from tests.source_snapshot_fixture import case_bytes, case_text
from tests.coffee_consolidation import (
    COFFEE_ROOT, coffee_parsed, coffee_symbols,
)

from pathlib import Path
from shutil import copytree

import pytest
from tree_sitter_language_pack import get_parser

from atlas.metrics.adapters import get_metric_adapter
from atlas.bootstrap import repository_service
from atlas.domain.models import ParsedFile, SourceFile, Symbol
from atlas.metrics.callables import callable_metrics
from atlas.parsing.parser import parse_file
from atlas.indexer import analyze_repository
from atlas.persistence.database import migrate_database


def parsed(language: str, code: str):
    file = parse_file(SourceFile("sample", Path("sample"), language, code.encode()))
    callable_metrics(file)
    return file


@pytest.mark.parametrize(
    ("language", "code", "expected"),
    [
        # These syntax discriminators are absent from coffee (see the ledger).
        ("python", case_text('metrics', 'callable_metrics-parameter_counts-python', 'sample'), [4]),
        ("javascript", case_text('metrics', 'callable_metrics-parameter_counts-javascript', 'sample'), [4]),
        ("python", case_text('metrics', 'callable_metrics-parameter_counts-python-2', 'sample'), [3]),
        ("python", case_text('metrics', 'callable_metrics-parameter_counts-python-3', 'sample'), [8, 1]),
        (
            "javascript",
            case_text('metrics', 'callable_metrics-parameter_counts-javascript-2', 'sample'),
            [1, 0, 2],
        ),

        (
            "go",
            case_text('metrics', 'callable_metrics-parameter_counts-go', 'sample'),
            [3, 2],
        ),
        ("rust", case_text('metrics', 'callable_metrics-parameter_counts-rust', 'sample'), [2]),
        ("rust", case_text('metrics', 'callable_metrics-parameter_counts-rust-2', 'sample'), [1]),
        ("rust", case_text('metrics', 'callable_metrics-parameter_counts-rust-3', 'sample'), [7]),
        ("rust", case_text('metrics', 'callable_metrics-parameter_counts-rust-4', 'sample'), [2]),
        ("rust", case_text('metrics', 'callable_metrics-parameter_counts-rust-5', 'sample'), [0, 2]),

        ("kotlin", case_text('metrics', 'callable_metrics-parameter_counts-kotlin', 'sample'), [2]),
        ("kotlin", case_text('metrics', 'callable_metrics-parameter_counts-kotlin-2', 'sample'), [2, 0]),

        ("elixir", case_text('metrics', 'callable_metrics-parameter_counts-elixir', 'sample'), [2]),
        (
            "elixir",
            case_text('metrics', 'callable_metrics-parameter_counts-elixir-2', 'sample'),
            [0, 2, 0],
        ),
    ],
)
def test_parameter_count_syntax_discriminators(language, code, expected):
    file = parsed(language, code)
    assert file.parse_error is None
    callables = [
        symbol for symbol in file.symbols if symbol.kind in {"function", "method"}
    ]
    assert [symbol.parameter_count for symbol in callables] == expected
    assert len(callables) == len(expected)
    assert all(symbol.line_count == 1 for symbol in callables)


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
    code = case_text('metrics', 'callable_metrics-python_receivers_only_in_methods-python', 'sample')
    symbols = parsed("python", code).symbols
    counts = {
        symbol.name: symbol.parameter_count
        for symbol in symbols
        if symbol.kind == "function"
    }
    assert counts == {
        "f": 2, "m": 1, "inner": 2, "c": 1, "s": 2, "v": 1,
        "renamed": 7, "renamed_class": 7, "commented_static": 8,
    }
    assert next(symbol for symbol in symbols if symbol.name == "m").line_count == 2


def test_comments_separators_and_annotations_are_not_inputs():
    assert (
        parsed(
            "python",
            case_text('metrics', 'callable_metrics-comments_separators_and_annotations_are_not_inputs-python', 'sample'),
        )
        .symbols[0]
        .parameter_count
        == 2
    )
    assert (
        parsed(
            "typescript",
            case_text('metrics', 'callable_metrics-comments_separators_and_annotations_are_not_inputs-typescript', 'sample'),
        )
        .symbols[0]
        .parameter_count
        == 2
    )


def test_unknown_counts_are_not_zero():
    assert (
        parsed("kotlin", case_text('metrics', 'callable_metrics-unknown_counts_are_not_zero-kotlin', 'sample')).symbols[0].parameter_count is None
    )
    adapter = get_metric_adapter("python")
    malformed = (
        get_parser("python").parse(case_bytes('metrics', 'callable_metrics-unknown_counts_are_not_zero-python', 'sample.py')).root_node.named_children[0]
    )
    assert adapter.parameter_count(malformed) is None
    assert (
        get_metric_adapter("ruby").parameter_count(
            get_parser("ruby").parse(case_bytes('metrics', 'callable_metrics-unknown_counts_are_not_zero-ruby', 'sample.rb')).root_node.named_children[0]
        )
        is None
    )


@pytest.mark.parametrize("name", ["brew", "retry"])
def test_elixir_clauses_keep_identity_and_counts(name):
    file = coffee_parsed("elixir", "brewing/brewer.ex")
    clauses = coffee_symbols(file, f"Coffee.Brewing.Brewer.{name}")
    assert [(symbol.name, symbol.parameter_count) for symbol in clauses] == [
        (name, 1), (name, 1),
    ]
    assert len({symbol.key for symbol in clauses}) == 2


def test_elixir_incomplete_lambda_count_is_unknown():
    assert (
        get_metric_adapter("elixir").parameter_count(
            get_parser("elixir")
            .parse(case_bytes('metrics', 'callable_metrics-elixir_clauses_keep_identity_and_counts-elixir-2', 'sample.ex'))
            .root_node.named_children[0]
        )
        is None
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python', 'sample.py'), 0),
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python-2', 'sample.py'), 1),
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python-3', 'sample.py'), 1),
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python-4', 'sample.py'), 1),
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python-5', 'sample.py'), 2),
        (case_bytes('metrics', 'callable_metrics-file_physical_lines-python-6', 'sample.py'), 2),
    ],
)
def test_file_physical_lines(tmp_path, content, expected):
    (tmp_path / "file.py").write_bytes(content)
    graph = analyze_repository(tmp_path)
    node = next(node for node in graph.nodes if node["type"] == "file")
    assert node["properties"]["lineCount"] == expected


def test_unknown_parameter_property_is_omitted(tmp_path):
    (tmp_path / "sample.rb").write_text(case_text('metrics', 'callable_metrics-unknown_parameter_property_is_omitted-ruby', 'sample.rb'))
    graph = analyze_repository(tmp_path)
    callable_node = next(
        node for node in graph.nodes if node["type"] in {"function", "method"}
    )
    assert callable_node["properties"]["lineCount"] == 1
    assert "parameterCount" not in callable_node["properties"]


def test_end_exclusive_column_zero_and_nested_physical_lines():
    code = case_text('metrics', 'callable_metrics-end_exclusive_column_zero_and_nested_physical_lines-python', 'sample')
    file = parsed("python", code)
    assert [(symbol.line_count, symbol.parameter_count) for symbol in file.symbols] == [
        (5, 1),
        (2, 1),
    ]
    symbol = Symbol(
        "key",
        "sample",
        "python",
        "f",
        "f",
        "function",
        "file:sample",
        0,
        6,
        1,
        1,
        3,
        1,
        None,
        None,
        [],
    )
    synthetic = ParsedFile(
        SourceFile("sample", Path("sample"), "python", case_bytes('metrics', 'callable_metrics-end_exclusive_column_zero_and_nested_physical_lines-python-2', 'sample.py')),
        "hash",
        None,
        [symbol],
    )
    callable_metrics(synthetic)
    assert symbol.line_count == 2


def test_metrics_survive_snapshot_persistence(tmp_path):
    root = tmp_path / "source"
    copytree(COFFEE_ROOT / "python", root)
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
