"""Real UI and XML receipt workflows distinguish components from intrinsic tags."""

import unittest
from dataclasses import replace

import pytest

from atlas.metrics.resolver import resolve_connections
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources
from tests.coffee_tsx_assertions import assert_component_references, assert_file_call_coordinates
from tests.variant_snapshot_support import VARIANT_ROOT, scenario_sources

WORKFLOW_CALLS = [
    ("App.tsx", "App", "label('espresso')", "CoffeeCard.tsx::label"),
    ("App.tsx", "Menu.addDrink", "basket.add(name, quantity)", "external:"),
    ("App.tsx", "Menu", "orderTotal(basket)", "Basket.tsx::orderTotal"),
    ("App.tsx", "CoffeeCounter.<anonymous>", "new Basket()", "Basket.tsx::Basket"),
    ("Basket.tsx", "startOrder", "basket.add(name, quantity)", "Basket.tsx::Basket.add"),
    ("CoffeeCard.tsx", "CoffeeCard.<anonymous>", "onOrder(name)", "external:"),
]


def assert_workflow_call(context, case):
    symbols, edges = context
    path, owner, evidence, target = case
    owned = [edge for edge in edges if edge.type == "CALLS" and edge.path == path
             and edge.evidence == evidence
             and symbols[edge.source_key].qualified_name == f"{path}::{owner}"]
    assert len(owned) == 1, case
    edge, = owned
    if target == "external:":
        assert edge.target_key.startswith(target), case
    else:
        assert symbols[edge.target_key].qualified_name == target, case


class TsxCoffeeTest(unittest.TestCase):
    def test_component_reference_ownership_and_normal_calls(self):
        repo = parse_files(coffee_sources("tsx"))
        self.assertEqual({file.source.language for file in repo.files}, {"tsx"})
        self.assertTrue(all(file.parse_error is None for file in repo.files))
        symbols = {symbol.key: symbol for symbol in repo.symbols}
        edges = resolve_connections(repo).connections
        assert_component_references(self, symbols, edges)
        intrinsics = {"main", "article", "h1", "h2", "p", "button", "section", "aside", "ul", "li", "output", "small"}
        self.assertFalse(any(call.name in intrinsics for call in repo.calls))

    def test_shared_workflow_calls_retain_source_and_owner(self):
        repo = parse_files(coffee_sources("tsx"))
        context = ({symbol.key: symbol for symbol in repo.symbols}, resolve_connections(repo).connections)
        for case in WORKFLOW_CALLS:
            assert_workflow_call(context, case)
        for file in repo.files:
            assert_file_call_coordinates(self, file)


@pytest.mark.parametrize("grammar", ["javascript", "tsx"])
def test_xml_receipt_intrinsics_fragments_closing_tags_and_shadowing(grammar):
    root = VARIANT_ROOT / "javascript" / "xml-receipt-preview"
    sources = [replace(source, language=grammar) if source.path == "preview/Receipt.jsx" else source
               for source in scenario_sources(root)]
    repo = parse_files(sources)
    file, = [file for file in repo.files if file.source.path == "preview/Receipt.jsx"]
    assert file.parse_error is None
    assert_xml_receipt_references(repo, file)


def assert_xml_receipt_references(repo, file):
    assert [(call.name, call.relationship) for call in file.calls] == [
        ("ReceiptCard", "REFERENCES"), ("ReceiptCard", "REFERENCES"),
    ]
    references = [edge for edge in resolve_connections(repo).connections
                  if edge.path == file.source.path and edge.type == "REFERENCES"]
    assert len(references) == 2
    symbols = {symbol.key: symbol for symbol in repo.symbols}
    assert symbols[references[0].target_key].qualified_name == "preview/Receipt.jsx::ReceiptCard"
    assert symbols[references[0].source_key].name == "ReceiptPreview"
    assert references[1].target_key.startswith("external:")
    assert symbols[references[1].source_key].name == "BrandedReceipt"
