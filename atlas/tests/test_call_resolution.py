"""Member, computed and ambiguous calls must not fall back to bare names."""

import pytest

from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import _extract_calls
from tests.import_project_support import analyze, project_sources

COLLISIONS = [
    ("python", "src/coffee/orders/reservations.py", "reserve(order)", "supplier.reserve(order)",
     "src/coffee/inventory/delivery.py", "delivery_label(order)", "supplier.delivery_label(order)"),
    ("typescript", "ordering/Reservations.ts", "reserve(order)", "supplier.reserve(order)",
     "inventory/Delivery.ts", "deliveryLabel(order)", "supplier.deliveryLabel(order)"),
    ("kotlin", "orders/Reservations.kt", "reserve(order)", "supplier.reserve(order)",
     "inventory/Delivery.kt", "deliveryLabel(it)", "supplier.deliveryLabel(order)"),
    ("java", "orders/Reservations.java", "reserve(order)", "supplier.reserve(order)",
     "inventory/Delivery.java", "deliveryLabel(order)", "supplier.deliveryLabel(order)"),
    ("go", "brewing/reservations.go", "Reserve(order)", "supplier.Reserve(order)",
     "reporting/delivery.go", "DeliveryLabel(order)", "supplier.DeliveryLabel(order)"),
    ("rust", "brewing/reservations.rs", "reserve(names, customer)", "supplier.reserve(names)",
     "brewing/delivery.rs", "delivery_label(names, customer)", "supplier.delivery_label(names, customer)"),
    ("csharp", "orders/Reservations.cs", "Reserve(customer, drink, units)", "supplier.Reserve(drink, units)",
     "inventory/Delivery.cs", "DeliveryLabel(customer, drink.Key, drink.Value)", "supplier.DeliveryLabel(customer, drink, units)"),
    ("ruby", "orders/reservations.rb", "reserve(customer, drink, units)", "supplier.reserve(drink, units)",
     "inventory/delivery.rb", "delivery_label(customer, drink, units)", "supplier.delivery_label(customer, drink, units)"),
]


def calls_at(artifact, path, evidence):
    calls = [edge for edge in artifact.edges
             if edge["type"] == "CALLS" and edge["path"] == path and edge["evidence"] == evidence]
    assert calls
    return calls


@pytest.mark.parametrize("case", COLLISIONS)
@pytest.mark.parametrize("location", ["local", "global"])
def test_member_collisions_never_use_local_or_global_name_fallback(tmp_path, case, location):
    language, path, local_call, local_member, delivery_path, delivery_call, delivery_member = case
    sources = project_sources(language, "member-collision")
    artifact = analyze(tmp_path, sources)
    member = local_member if location == "local" else delivery_member
    control_path, control = (path, local_call) if location == "local" else (delivery_path, delivery_call)
    member_calls = calls_at(artifact, path, member)
    assert all(edge["targetStableKey"].startswith("external:") for edge in member_calls)
    bare_calls = calls_at(artifact, control_path, control)
    assert all(edge["targetStableKey"].startswith("symbol:") for edge in bare_calls)
    assert_call_evidence(member_calls + bare_calls, sources)


def assert_call_evidence(calls, sources):
    assert all(edge["evidence"] is not None and edge["evidence"] in sources[edge["path"]] for edge in calls)


def test_computed_and_qualified_targets_are_not_bare(tmp_path):
    sources = project_sources("typescript", "computed-receipt-calls")
    analyze(tmp_path, sources)
    source = next(source for source in discover_files(tmp_path) if source.path == "ordering/receipt.ts")
    calls = _extract_calls(source)
    assert calls
    for call in calls:
        assert call.bare_target == (call.name in {"factory", "helper"} and call.evidence in {"factory()", "helper()"})
        assert source.source[call.start_byte:call.end_byte].decode() == call.evidence
    computed, = [call for call in calls if call.evidence == "handlers[key](argument)"]
    assert computed.name == "handlers[key]"


def test_ambiguous_bare_call_stays_external(tmp_path):
    sources = project_sources("typescript", "ambiguous-roast-call")
    artifact = analyze(tmp_path, sources)
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS" and edge["path"] == "brewing/tasting.ts"]
    assert len(calls) == 1
    assert calls[0]["evidence"] == "roast()"
    assert calls[0]["targetStableKey"] == "external:typescript:callable:roast"


def test_query_from_does_not_resolve_to_receipt_factory(tmp_path):
    sources = project_sources("kotlin", "query-receipt-collision")
    artifact = analyze(tmp_path, sources)
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS" and edge["path"] == "inventory/StockRepository.kt"]
    assert calls
    assert any(edge["evidence"] is not None and '.from("stock")' in edge["evidence"] for edge in calls)
    assert all(edge["targetStableKey"].startswith("external:") for edge in calls)
