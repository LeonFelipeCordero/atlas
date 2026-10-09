"""JSX usages are references, not immediate calls or intrinsic HTML dependencies."""

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
        assert_component_references(self, repo, symbols, edges)

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
                    ("REFERENCES", "App", "CoffeeCard", 7, "CoffeeCard"): 1,
                    ("REFERENCES", "App", "Cards.CoffeeCard", 8, "CoffeeCard"): 1,
                    ("REFERENCES", "Preview", "CoffeeCard", 15, "external"): 1,
                    ("CALLS", "App", "label('espresso')", 7, "label"): 1,
                    ("CALLS", "CoffeeCard", "label(name)", 10, "label"): 1,
                }
            ),
        )
        for file in repo.files:
            assert_file_call_coordinates(self, file)

    def test_lowercase_namespaces_and_nonletter_component_names(self):
        repo = repository(
            "tsx",
            {
                "Card.tsx": "export function Card() { return <div />; }",
                "App.tsx": """import * as cards from './Card';
import {Card as $Card} from './Card';
import {Card as _Card} from './Card';
export function App() { return <><cards.Card /><$Card /><_Card /></>; }
""",
            },
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
                repo = repository(
                    language,
                    {
                        f"Card.{extension}": "export function Card() { return <div />; }",
                        f"App.{extension}": """import {Card} from './Card';
export function App() { return <><Card></Card><div /><custom-card /><svg:path /></>; }
export function Shadow(Card) { return <Card />; }
""",
                    },
                )
                assert_intrinsics_and_shadowing(self, repo)


if __name__ == "__main__":
    unittest.main()
