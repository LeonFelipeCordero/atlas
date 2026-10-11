"""Focused JSX ownership and source-coordinate assertions."""

from atlas.metrics.resolver import resolve_connections


def reference_edges(edges):
    return [edge for edge in edges if edge.type == "REFERENCES"]


def owned_references(references, symbols, name):
    return [
        edge
        for edge in references
        if edge.source_key in symbols and symbols[edge.source_key].name == name
    ]


def assert_component_references(test, symbols, edges):
    references = reference_edges(edges)
    owned = owned_references(references, symbols, "App")
    test.assertEqual(len(owned), 2)
    test.assertEqual(
        {edge.evidence for edge in owned}, {"CoffeeCard", "Cards.CoffeeCard"}
    )
    test.assertTrue(
        all(symbols[edge.target_key].name == "CoffeeCard" for edge in owned)
    )
    preview = owned_references(references, symbols, "Preview")
    test.assertEqual(len(preview), 1)
    test.assertTrue(preview[0].target_key.startswith("external:"))
    menu = owned_references(references, symbols, "Menu")
    test.assertEqual({edge.evidence for edge in menu}, {"cards.CoffeeCard", "$Card", "_Card"})
    test.assertEqual(len(menu), 3)
    test.assertTrue(all(symbols[edge.target_key].name == "CoffeeCard" for edge in menu))
    counter = owned_references(references, symbols, "CoffeeCounter")
    test.assertEqual(len(counter), 1)
    test.assertEqual(symbols[counter[0].target_key].name, "Menu")
    test.assertEqual(len(references), 7)
    assert_normal_calls(test, symbols, edges)


def assert_normal_calls(test, symbols, edges):
    label_calls = [
        edge
        for edge in edges
        if edge.type == "CALLS" and "label(" in (edge.evidence or "")
    ]
    test.assertEqual(len(label_calls), 2)
    test.assertTrue(
        all(symbols[edge.target_key].name == "label" for edge in label_calls)
    )


def assert_file_call_coordinates(test, file):
    source = file.source.source
    for call in file.calls:
        with test.subTest(path=file.source.path, evidence=call.evidence):
            test.assertEqual(
                source[call.start_byte : call.end_byte].decode(), call.evidence
            )
            test.assertEqual(source[: call.start_byte].count(b"\n") + 1, call.line)


def assert_intrinsics_and_shadowing(test, repo):
    test.assertEqual([call.name for call in repo.calls], ["Card", "Card"])
    test.assertTrue(all(call.relationship == "REFERENCES" for call in repo.calls))
    references = reference_edges(resolve_connections(repo).connections)
    test.assertEqual(len(references), 2)
    test.assertEqual(
        sum(edge.target_key.startswith("symbol:") for edge in references), 1
    )
