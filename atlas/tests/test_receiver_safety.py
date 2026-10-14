"""Whole coffee projects: receiver identity, visibility and unsafe lifetimes."""

import pytest

from tests.import_project_support import project_sources
from tests.test_semantic_resolution import (
    assert_call_source,
    assert_coffee_call,
    call_edges,
    coffee_owner_keys,
    coffee_symbols,
    repository,
)


def assert_target(language, sources, expected):
    evidence, internal = expected
    edges = call_edges(repository(language, sources), evidence)
    assert edges, evidence
    assert all(
        (e.target_key.startswith("symbol:" if internal else "external:") for e in edges)
    ), edges


def assert_lifetime_call(language, site, target=None):
    """Resolve one workflow site, including its owner and exact declaration."""
    path, owner, evidence = site
    repo = repository(language, project_sources(language, "receiver-lifetime"))
    target_path, target_name = target or (
        None, f"external:{language}:callable:{evidence.split('(')[0].rsplit('.', 1)[-1]}"
    )
    return assert_coffee_call(repo, (path, owner, evidence, target_path, target_name))


PY_LEDGER = "src/coffee/inventory/ledger.py"
PY_INTAKE = "src/coffee/orders/reservations.py"
JAVA_INTAKE = "intake/ReservationIntake.java"
KOTLIN_INTAKE = "intake/ReservationIntake.kt"
GO_LEDGER = "reservations/ledger.go"
RUST_INTAKE = "reservation_intake.rs"


@pytest.mark.parametrize(
    "case",
    [
        ("python", PY_LEDGER, "InjectedStation.fulfill", "self.ledger.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
        ("python", PY_LEDGER, "StableStation.fulfill", "self.ledger.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
        ("python", PY_LEDGER, "OpeningStation.fulfill", "self.ledger.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
        ("javascript", "reservations/Ledger.js", "OpeningStation.fulfill", "this.ledger.commit(order)", ("reservations/Ledger.js", "ReservationLedger.commit")),
        ("javascript", "reservations/PickupPanel.jsx", "PickupPanel.fulfill", "this.ledger.commit(order)", ("reservations/Ledger.js", "ReservationLedger.commit")),
        ("java", JAVA_INTAKE, "ReservationIntake.open", "local.commit(order)", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
        ("java", JAVA_INTAKE, "ReservationIntake.opening", "openingLedger.commit(order)", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
        ("kotlin", KOTLIN_INTAKE, "openPickup", "ledger.commit(order)", ("reservations/ReservationLedger.kt", "ReservationLedger.commit")),
        ("go", GO_LEDGER, "Fulfill", "station.ledger.Commit(order)", (GO_LEDGER, "Commit")),
        ("rust", RUST_INTAKE, "PickupStation.fulfill", "self.ledger.commit(order)", (RUST_INTAKE, "ReservationLedger.commit")),
    ],
)
def test_constructor_and_field_receivers(case):
    language, path, owner, evidence, target = case
    assert_lifetime_call(language, (path, owner, evidence), target)


@pytest.mark.parametrize(
    "case",
    [
        ("python", PY_INTAKE, "redirect_declared", "ledger.commit(order)"),
        ("python", "src/coffee/orders/vendor_intake.py", "receive_remote", "ledger.commit(order)"),
        ("python", PY_INTAKE, "receive_before_opening", "ledger.commit(order)"),
        ("python", PY_INTAKE, "open_on_demand", "ledger.commit(order)"),
        ("python", PY_INTAKE, "open_declared_on_demand", "ledger.commit(order)"),
        ("python", PY_LEDGER, "RecoveryStation.redirect", "self.ledger.commit(order)"),
        ("python", PY_LEDGER, "RemoteRecoveryStation.replace_station", "self.ledger.commit(order)"),
        ("python", PY_INTAKE, "restore_batch", "ledger.commit(order)"),
        ("javascript", "reservations/Ledger.js", "RecoveryStation.redirect", "this.ledger.commit(order)"),
        ("javascript", "reservations/VendorMigration.js", "replaceMember", "ledger.commit(order)"),
        ("javascript", "reservations/Intake.js", "advanceReceiver", "ledger.commit(order)"),
        ("javascript", "reservations/Intake.js", "restoreBatch", "ledger.commit(order)"),
        ("java", JAVA_INTAKE, "StaticDispatch.fulfill", "ledger.commit(order)"),
        ("java", JAVA_INTAKE, "ReservationIntake.shadow", "ledger.commit(order)"),
        ("kotlin", KOTLIN_INTAKE, "TemporaryIntake.fulfill", "ledger.commit(order)"),
        ("rust", RUST_INTAKE, "restore", "ledger.commit(order)"),
        ("go", GO_LEDGER, "ReceiveDynamic", "ledger.Commit(order)"),
        *[(language, f"reservations/Intake.{ext}", "receiveUnion", "ledger.commit(order)")
          for language, ext in (("typescript", "ts"), ("tsx", "tsx"))],
    ],
)
def test_unsafe_receivers_stay_external(case):
    language, *site = case
    assert_lifetime_call(language, site)


@pytest.mark.parametrize(
    "case",
    [
        ("python", PY_INTAKE, "fulfill", "ledger.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
        ("java", JAVA_INTAKE, "ReservationIntake.fulfill", "ledger.commit(order)", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
        ("kotlin", KOTLIN_INTAKE, "ReservationIntake.fulfill", "ledger.commit(order)", ("reservations/ReservationLedger.kt", "ReservationLedger.commit")),
        ("go", "intake/orders.go", "Fulfill", "ledger.Commit(order)", (GO_LEDGER, "Commit")),
        ("rust", RUST_INTAKE, "receive_qualified", "ledger.commit(order)", (RUST_INTAKE, "ReservationLedger.commit")),
        *[(language, f"reservations/Intake.{ext}", "fulfill", "ledger.commit(order)", (f"reservations/Ledger.{ext}", "ReservationLedger.commit"))
          for language, ext in (("typescript", "ts"), ("tsx", "tsx"))],
    ],
)
def test_type_visibility_follows_import_and_namespace_context(case):
    language, path, owner, evidence, target = case
    assert_lifetime_call(language, (path, owner, evidence), target)


@pytest.mark.parametrize("language,ext", [("javascript", "js"), ("typescript", "ts"), ("tsx", "tsx")])
def test_imported_receiver_member_rebinding_is_not_ignored(language, ext):
    assert_lifetime_call(language, (f"reservations/Intake.{ext}", "installVendor", "ledger.commit(order)"))


def test_imported_python_receiver_member_rebinding_is_not_ignored():
    assert_lifetime_call("python", ("src/coffee/orders/vendor_intake.py", "install_vendor", "ledger.commit(order)"))


def test_constructor_injected_order_created_client():
    assert_lifetime_call("java", (JAVA_INTAKE, "ReservationIntake.fulfill", "ledger.commit(order)"),
                         ("reservations/ReservationLedger.java", "ReservationLedger.commit"))
    assert_lifetime_call("java", (JAVA_INTAKE, "ReservationIntake.fulfill", "client.sendAndWait(saved)"),
                         ("reservations/OrderCreatedClient.java", "OrderCreatedClient.sendAndWait"))


def test_audit_receiver_selects_one_argument_overload():
    repo = repository("java", project_sources("java", "receiver-lifetime"))
    evidence = "ledger.commit(order)"
    assert_call_source(repo, (JAVA_INTAKE, evidence))
    owners = coffee_owner_keys(repo, (JAVA_INTAKE, "AuditedIntake.fulfill"))
    overloads = coffee_symbols(repo, JAVA_INTAKE, "AuditLedger.commit")
    assert {symbol.signature for symbol in overloads} == {
        "Order commit(Order order)", "Order commit(Order order, String reason)",
    }
    target, = [symbol for symbol in overloads if symbol.signature == "Order commit(Order order)"]
    edge, = [edge for edge in call_edges(repo, evidence) if edge.source_key in owners]
    assert edge.target_key == target.key


def test_unrelated_constructor_assignments_are_separate_scopes():
    assert_lifetime_call("python", (PY_LEDGER, "OpeningStation.fulfill", "self.ledger.commit(order)"),
                         (PY_LEDGER, "ReservationLedger.commit"))


def test_unimported_type_is_not_guessed_globally():
    assert_lifetime_call("python", ("src/coffee/orders/unconfigured_intake.py", "receive", "ledger.commit(order)"))
