"""Standalone exact-target snapshots from the complete physical coffee projects."""

import pytest

from tests.coffee_fixture import coffee_graph, coffee_snapshot


SNAPSHOTS = {
    "go": [
        ("DirectLedger", "ledger.Record()", "symbol:receiver_samples/receivers.go::Record:81"),
        ("PointerLedger", "ledger.Flush()", "symbol:receiver_samples/receivers.go::Flush:121"),
        ("PairedLiterals", "ledger.Record()", "symbol:receiver_samples/receivers.go::Record:81"),
        ("PairedLiterals", "other.Record()", "symbol:receiver_samples/receivers.go::Record:161"),
        ("FactoryLedger", "NewLedger()", "symbol:receiver_samples/receivers.go::NewLedger:200"),
        ("FactoryLedger", "ledger.Record()", "external:go:callable:Record"),
        ("FactoryPair", "LedgerPair()", "symbol:receiver_samples/receivers.go::LedgerPair:258"),
        ("FactoryPair", "ledger.Record()", "external:go:callable:Record"),
        ("FactoryPair", "other.Record()", "external:go:callable:Record"),
        ("ReassignedLedger", "NewLedger()", "symbol:receiver_samples/receivers.go::NewLedger:200"),
        ("ReassignedLedger", "ledger.Record()", "external:go:callable:Record"),
        ("ShadowedLedger", "NewLedger()", "symbol:receiver_samples/receivers.go::NewLedger:200"),
        ("ShadowedLedger", "ledger.Record()", "external:go:callable:Record"),
        ("ShadowedLedger", "ledger.Record()", "external:go:callable:Record"),
        ("DereferencedLedger", "ledger.Record()", "external:go:callable:Record"),
    ],
    "rust": [
        ("direct_ledger", "ledger.record()", "symbol:receiver_samples.rs::LiteralLedger.record:143"),
        ("mutable_ledger", "ledger.flush()", "symbol:receiver_samples.rs::LiteralLedger.flush:167"),
        ("other_ledger", "ledger.record()", "symbol:receiver_samples.rs::OtherLedger.record:216"),
        ("associated_factory", "LiteralLedger::new()", "symbol:receiver_samples.rs::LiteralLedger.new:100"),
        ("associated_factory", "ledger.record()", "external:rust:callable:record"),
        ("reassigned_ledger", "LiteralLedger::new()", "symbol:receiver_samples.rs::LiteralLedger.new:100"),
        ("reassigned_ledger", "ledger.record()", "external:rust:callable:record"),
        ("shadowed_ledger", "LiteralLedger::new()", "symbol:receiver_samples.rs::LiteralLedger.new:100"),
        ("shadowed_ledger", "ledger.record()", "external:rust:callable:record"),
        ("shadowed_ledger", "ledger.record()", "symbol:receiver_samples.rs::LiteralLedger.record:143"),
        ("trait_ledger", "ledger.audit()", "external:rust:callable:audit"),
        ("associated_instance_method", "LiteralLedger::record(&LiteralLedger { count: 0 })", "external:rust:callable:record"),
        ("destructured_ledger", "ledger.record()", "external:rust:callable:record"),
        ("LiteralLedger.consume", "self.record()", "symbol:receiver_samples.rs::LiteralLedger.record:143"),
        ("associated_typed_receiver", "LiteralLedger::consume(ledger)", "external:rust:callable:consume"),
    ],
}


@pytest.mark.parametrize("language,path", [
    ("go", "receiver_samples/receivers.go"),
    ("rust", "receiver_samples.rs"),
])
def test_literal_receiver_targets_snapshot(language, path):
    graph = coffee_snapshot(coffee_graph(language))
    nodes = {node["stableKey"]: node for node in graph["nodes"]}
    actual = [
        (nodes[edge["sourceStableKey"]]["qualifiedName"].split("::", 1)[1],
         edge["evidence"], edge["targetStableKey"])
        for edge in graph["edges"] if edge["type"] == "CALLS" and edge["path"] == path
    ]
    assert actual == SNAPSHOTS[language]
