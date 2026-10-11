"""JSX usages are references, not immediate calls or intrinsic HTML dependencies."""

from tests.import_snapshot_support import import_case_sources as case_sources

import unittest
from collections import Counter
from pathlib import Path

from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_files
from atlas.metrics.resolver import resolve_connections
from tests.test_semantic_resolution import repository
from tests.coffee_tsx_assertions import (
    assert_component_references,
    assert_file_call_coordinates,
    assert_intrinsics_and_shadowing,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures/coffee/tsx"


class TsxCoffeeTest(unittest.TestCase):
    def test_component_reference_ownership_and_normal_calls(self):
        repo = parse_files(discover_files(FIXTURE))
        self.assertEqual({file.source.language for file in repo.files}, {"tsx"})
        self.assertTrue(all(file.parse_error is None for file in repo.files))
        symbols = {symbol.key: symbol for symbol in repo.symbols}
        edges = resolve_connections(repo).connections
        assert_component_references(self, symbols, edges)
        intrinsics = {"main", "article", "h1", "h2", "p", "button", "section", "aside", "ul", "li", "output"}
        self.assertFalse(any(call.name in intrinsics for call in repo.calls))

    def test_fixture_references_and_attribute_calls_retain_source_and_owner(self):
        repo = parse_files(discover_files(FIXTURE))
        symbols = {symbol.key: symbol.name for symbol in repo.symbols}
        graph = resolve_connections(repo)
        actual = Counter(
            (
                edge.type,
                symbols.get(edge.source_key),
                edge.evidence,
                edge.line,
                symbols.get(edge.target_key, "external"),
            )
            for edge in graph.connections
            if edge.type in {"REFERENCES", "CALLS"}
        )
        self.assertEqual(
            actual,
            Counter(
                {
                    ("REFERENCES", "App", "CoffeeCard", 12, "CoffeeCard"): 1,
                    ("REFERENCES", "App", "Cards.CoffeeCard", 13, "CoffeeCard"): 1,
                    ("REFERENCES", "Preview", "CoffeeCard", 20, "external"): 1,
                    ("REFERENCES", "Menu", "cards.CoffeeCard", 32, "CoffeeCard"): 1,
                    ("REFERENCES", "Menu", "$Card", 33, "CoffeeCard"): 1,
                    ("REFERENCES", "Menu", "_Card", 34, "CoffeeCard"): 1,
                    ("REFERENCES", "CoffeeCounter", "Menu", 46, "Menu"): 1,
                    ("CALLS", "App", "label('espresso')", 12, "label"): 1,
                    ("CALLS", "Menu", "useState<BasketItem[]>(() => basket.snapshot())", 24, "external"): 1,
                    ("CALLS", "<anonymous>", "basket.snapshot()", 24, "external"): 1,
                    ("CALLS", "addDrink", "basket.add(name, quantity)", 26, "external"): 1,
                    ("CALLS", "addDrink", "setItems(basket.snapshot())", 27, "external"): 1,
                    ("CALLS", "addDrink", "basket.snapshot()", 27, "external"): 1,
                    ("CALLS", "<anonymous>", "addDrink(name)", 33, "addDrink"): 1,
                    ("CALLS", "Menu", "items.map(({ name, quantity }) => <li key={name}>{quantity} x {name}</li>)", 37, "external"): 1,
                    ("CALLS", "Menu", "orderTotal(basket).toFixed(2)", 38, "external"): 1,
                    ("CALLS", "Menu", "orderTotal(basket)", 38, "orderTotal"): 1,
                    ("CALLS", "CoffeeCounter", "useState<Basket>(() => new Basket())", 45, "external"): 1,
                    ("CALLS", "<anonymous>", "new Basket()", 45, "Basket"): 1,
                    ("CALLS", "add", "this.items.find(item => item.name === name)", 12, "external"): 1,
                    ("CALLS", "add", "this.items.push({ name, quantity })", 14, "external"): 1,
                    ("CALLS", "total", "this.items.reduce((sum, { name, quantity }) => sum + this.prices[name] * quantity, 0)", 18, "external"): 1,
                    ("CALLS", "total", "fees.reduce((sum, fee) => sum + fee, 0)", 19, "external"): 1,
                    ("CALLS", "snapshot", "this.items.map(item => ({ ...item }))", 23, "external"): 1,
                    ("CALLS", "startOrder", "new Basket()", 28, "Basket"): 1,
                    ("CALLS", "startOrder", "basket.add(name, quantity)", 29, "add"): 1,
                    ("CALLS", "orderTotal", "basket.total(discount)", 34, "total"): 1,
                    ("CALLS", "CoffeeCard", "label(name)", 16, "label"): 1,
                    ("CALLS", "CoffeeCard", "price.toFixed(2)", 17, "external"): 1,
                    ("CALLS", "<anonymous>", "onOrder(name)", 18, "external"): 1,
                }
            ),
        )
        for file in repo.files:
            assert_file_call_coordinates(self, file)

    def test_lowercase_namespaces_and_nonletter_component_names(self):
        repo = repository(
            "tsx",
            case_sources("imports", "tsx-coffee-lowercase-namespaces-and-nonletter-component-names"),
        )
        references = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "REFERENCES"
        ]
        self.assertEqual(len(references), 3)
        self.assertTrue(
            all(
                edge.target_key.startswith("symbol:Card.tsx::Card:")
                for edge in references
            )
        )

    def test_jsx_intrinsics_fragments_closing_tags_and_shadowing(self):
        for language, extension in [("javascript", "jsx"), ("tsx", "tsx")]:
            with self.subTest(language=language):
                repo = repository(language, case_sources("imports", "jsx-intrinsics-" + extension))
                assert_intrinsics_and_shadowing(self, repo)


if __name__ == "__main__":
    unittest.main()
