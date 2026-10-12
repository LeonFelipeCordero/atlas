"""Order workflow regressions: writes, aliases and inherent method identity."""

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


@pytest.mark.parametrize("language,path,owner", [
    ("java", JAVA_INTAKE, "ReservationIntake.redirect"),
    ("kotlin", KOTLIN_INTAKE, "redirect"),
    ("typescript", "reservations/Intake.ts", "redirectDeclared"),
    ("tsx", "reservations/Intake.tsx", "redirectDeclared"),
])
def test_reassigned_declared_receiver_is_not_trusted(language, path, owner):
    evidence = "local.commit(order)" if language == "java" else "ledger.commit(order)"
    assert_lifetime_call(language, (path, owner, evidence))


@pytest.mark.parametrize("owner,evidence", [
    ("replace_field", "station.ledger.commit(order)"),
    ("replace_alias", "station.ledger.commit(order)"),
    ("replace_chain", "station.ledger.commit(order)"),
    ("write_original", "alias.ledger.commit(order)"),
    ("install_adapter", "station.ledger.commit(order)"),
])
def test_python_caller_field_writes_invalidate_receiver(owner, evidence):
    assert_lifetime_call("python", (PY_INTAKE, owner, evidence))


@pytest.mark.parametrize("language,ext", [("javascript", "js"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("owner", ["replaceField", "replaceAlias"])
def test_script_caller_field_writes_invalidate_receiver(language, ext, owner):
    assert_lifetime_call(language, (f"reservations/Intake.{ext}", owner, "station.ledger.commit(order)"))


@pytest.mark.parametrize("owner", ["migrate_vendor", "migrate_dotted"])
def test_python_member_mutation_follows_imported_class_identity(owner):
    assert_lifetime_call("python", ("src/coffee/orders/vendor_intake.py", owner, "ledger.commit(order)"))


@pytest.mark.parametrize("language,ext", [("typescript", "ts"), ("tsx", "tsx")])
def test_script_member_mutation_follows_imported_class_identity(language, ext):
    assert_lifetime_call(language, (f"reservations/Intake.{ext}", "migrateVendor", "ledger.commit(order)"))


@pytest.mark.parametrize("case", [
    ("python", PY_INTAKE, "fulfill_unchanged", "station.ledger.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
    ("javascript", "reservations/Intake.js", "fulfillUnchanged", "station.ledger.commit(order)", ("reservations/Ledger.js", "ReservationLedger.commit")),
    *[(language, f"reservations/Intake.{ext}", "fulfillDeclared", "ledger.commit(order)", (f"reservations/Ledger.{ext}", "ReservationLedger.commit"))
      for language, ext in (("typescript", "ts"), ("tsx", "tsx"))],
])
def test_unchanged_receivers_remain_internal(case):
    language, path, owner, evidence, target = case
    assert_lifetime_call(language, (path, owner, evidence), target)


@pytest.mark.parametrize("owner,target_path,target", [
    ("receive_qualified", RUST_INTAKE, "ReservationLedger.commit"),
    ("deliver", "reservation_intake/delivery.rs", "<anonymous>.commit"),
    ("archive", RUST_INTAKE, "archive_writer.ArchiveLedger.commit"),
])
def test_rust_impl_in_another_module_resolves_identity(owner, target_path, target):
    assert_lifetime_call("rust", (RUST_INTAKE, owner, "ledger.commit(order)"), (target_path, target))


@pytest.mark.parametrize("owner", ["read_archived", "audit", "reconcile"])
def test_rust_unrelated_duplicate_and_trait_impl_members_stay_external(owner):
    assert_lifetime_call("rust", (RUST_INTAKE, owner, "ledger.commit(order)"))


def test_java_constructor_subtype_field_write_is_not_trusted():
    assert_lifetime_call("java", (JAVA_INTAKE, "DeliveryStation.fulfill", "ledger.commit(order)"))


def test_rust_impl_target_is_the_actual_method():
    assert_lifetime_call("rust", (RUST_INTAKE, "receive_qualified", "ledger.commit(order)"),
                         (RUST_INTAKE, "ReservationLedger.commit"))


@pytest.mark.parametrize("case", [
    ("python", PY_INTAKE, "visit_batch", "visit_batch.visit", "station.commit(order)", (PY_LEDGER, "ReservationLedger.commit")),
    ("javascript", "reservations/Intake.js", "visitBatch", "visitBatch.visit", "station.commit(order)", ("reservations/Ledger.js", "ReservationLedger.commit")),
    ("typescript", "reservations/Intake.ts", "visitBatch", "visitBatch.visit", "station.commit(order)", ("reservations/Ledger.ts", "ReservationLedger.commit")),
    ("tsx", "reservations/Intake.tsx", "visitBatch", "visitBatch.visit", "station.commit(order)", ("reservations/Ledger.tsx", "ReservationLedger.commit")),
    ("go", GO_LEDGER, "VisitBatch", "VisitBatch.visit", "ledger.Commit(order)", (GO_LEDGER, "Commit")),
    ("kotlin", KOTLIN_INTAKE, "visitBatch", "visitBatch.<anonymous>", "ledger.commit(order)", ("reservations/ReservationLedger.kt", "ReservationLedger.commit")),
    ("java", JAVA_INTAKE, "ReservationIntake.visit", "ReservationIntake.visit.<anonymous>", "local.commit(order)", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
    ("java", JAVA_INTAKE, "ReservationIntake.visitInferred", "ReservationIntake.visitInferred.<anonymous>", "local.commit(order)", ("reservations/ReservationLedger.java", "ReservationLedger.commit")),
])
def test_callback_bindings_do_not_inherit_or_poison_outer_receiver(case):
    language, path, outer, callback, evidence, target = case
    assert_lifetime_call(language, (path, callback, evidence))
    assert_lifetime_call(language, (path, outer, evidence), target)


@pytest.mark.parametrize("owner", ["ReservationIntake.visitTyped", "ReservationIntake.visitFinal"])
def test_typed_java_callback_receiver_has_its_own_identity(owner):
    target = ("reservations/ReservationLedger.java", "ReservationLedger.commit")
    for scope in (owner, f"{owner}.<anonymous>"):
        assert_lifetime_call("java", (JAVA_INTAKE, scope, "local.commit(order)"), target)
