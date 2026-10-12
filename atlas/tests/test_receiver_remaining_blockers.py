"""Whole order projects: alias writes, initializer identity and compound updates."""

import pytest

from tests.test_receiver_safety import (
    GO_LEDGER,
    JAVA_INTAKE,
    KOTLIN_INTAKE,
    PY_INTAKE,
    PY_LEDGER,
    RUST_INTAKE,
    assert_lifetime_call,
)


@pytest.mark.parametrize("case", [
    ("python", PY_LEDGER, "PickupStation.transfer", "self.ledger.commit(order)"),
    ("python", PY_LEDGER, "PickupWindow.transfer", "self.station.ledger.commit(order)"),
    ("javascript", "reservations/Ledger.js", "PickupStation.transfer", "this.ledger.commit(order)"),
    ("typescript", "reservations/Ledger.ts", "PickupStation.transfer", "this.ledger.commit(order)"),
    ("tsx", "reservations/Ledger.tsx", "PickupStation.transfer", "this.ledger.commit(order)"),
    ("go", GO_LEDGER, "Transfer", "station.ledger.Commit(order)"),
])
def test_alias_field_mutation(case):
    language, *site = case
    assert_lifetime_call(language, site)


@pytest.mark.parametrize("language_case", [("javascript", "js"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("scope", ["Prototype", "Instance"])
@pytest.mark.parametrize("operation", ["retain", "fallback", "initialize", "append", "advance"])
def test_script_member_write_forms(language_case, scope, operation):
    language, ext = language_case
    assert_lifetime_call(language, (f"reservations/vendor/{operation}{scope}.{ext}", f"{operation}{scope}", "ledger.commit(order)"))


@pytest.mark.parametrize("language_case", [("python", "py"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("same", [False, True])
@pytest.mark.parametrize("initializer", ["constructor", "identifier"])
def test_annotated_initializer_identity(language_case, same, initializer):
    language, ext = language_case
    if language == "python":
        owner = ("open_" if initializer == "constructor" else "resume_") + ("pickup" if same else "delivery")
        path, target_path = PY_INTAKE, PY_LEDGER
    else:
        owner = ("open" if initializer == "constructor" else "resume") + ("Pickup" if same else "Delivery")
        path, target_path = f"reservations/Intake.{ext}", f"reservations/Ledger.{ext}"
    target = (target_path, "ReservationLedger.commit") if same else None
    assert_lifetime_call(language, (path, owner, "ledger.commit(order)"), target)


@pytest.mark.parametrize("case", [
    ("python", PY_INTAKE, "open_alias", (PY_LEDGER, "ReservationLedger.commit")),
    ("typescript", "reservations/Intake.ts", "openAlias", ("reservations/Ledger.ts", "ReservationLedger.commit")),
    ("tsx", "reservations/Intake.tsx", "openAlias", ("reservations/Ledger.tsx", "ReservationLedger.commit")),
    ("java", JAVA_INTAKE, "ReservationIntake.receive", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
    ("kotlin", KOTLIN_INTAKE, "receive", ("reservations/ReservationLedger.kt", "ReservationLedger.commit")),
    ("kotlin", KOTLIN_INTAKE, "openAlias", ("reservations/ReservationLedger.kt", "ReservationLedger.commit")),
])
def test_import_alias_identity_and_static_parameter_types(case):
    language, path, owner, target = case
    evidence = "parameter.commit(order)" if language == "java" else "ledger.commit(order)"
    assert_lifetime_call(language, (path, owner, evidence), target)


@pytest.mark.parametrize("path,owner,target", [
    (RUST_INTAKE, "ReservationLedger.fulfill", "ReservationLedger.commit"),
    ("reservation_intake/delivery.rs", "<anonymous>.fulfill", "<anonymous>.commit"),
    (RUST_INTAKE, "PickupStatus.fulfill", "PickupStatus.commit"),
    ("reservation_intake/delivery_status.rs", "<anonymous>.fulfill", "<anonymous>.commit"),
])
def test_rust_self_impl_identity(path, owner, target):
    assert_lifetime_call("rust", (path, owner, "self.commit(order)"), (path, target))


@pytest.mark.parametrize("language,path,owner", [
    ("rust", RUST_INTAKE, "adjust"),
    ("go", GO_LEDGER, "Adjust"),
    ("go", GO_LEDGER, "Advance"),
    ("java", JAVA_INTAKE, "ReservationIntake.advance"),
    ("kotlin", KOTLIN_INTAKE, "advance"),
    ("kotlin", KOTLIN_INTAKE, "advanceBefore"),
])
def test_compound_receiver_assignment(language, path, owner):
    receiver = "local" if language == "java" else "ledger"
    method = "Commit" if language == "go" else "commit"
    assert_lifetime_call(language, (path, owner, f"{receiver}.{method}(order)"))


def test_go_block_shadow_is_not_a_declared_receiver():
    assert_lifetime_call("go", (GO_LEDGER, "Restore", 'ledger.Commit("recovery:" + order)'))


def test_go_range_binding_does_not_leak():
    assert_lifetime_call("go", (GO_LEDGER, "VisitRange", 'ledger.Commit("batch:" + order)'))
    assert_lifetime_call("go", (GO_LEDGER, "VisitRange", "ledger.Commit(order)"), (GO_LEDGER, "Commit"))
