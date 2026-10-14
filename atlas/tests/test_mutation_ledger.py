"""Mutation persistence, append-only trials, source checks and graph independence."""

import sqlite3
from pathlib import Path

import pytest

from atlas.bootstrap import migrate_database, mutation_service, repository_service
from atlas.domain.mutation import MutationTrial
from atlas.domain.repositories import RepositoryError
from atlas.persistence.mutation_repository import mutation_store
from atlas.services.mutation import source_status
from tests.graph_storage_fixture import graph_artifact
from tests.mutation_support import SOURCE, ledger_session, trial_input


@pytest.fixture
def ledger(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "source"
    root.mkdir()
    (root / "payments.py").write_bytes(SOURCE)
    database = tmp_path / "ledger.sqlite"
    migrate_database(database)
    with mutation_store(database) as store:
        store.save_session(ledger_session(root))
    return root, database


def test_snapshots_and_multiple_trials_round_trip(ledger: tuple[Path, Path]) -> None:
    root, database = ledger
    with mutation_service(database) as service:
        first = service.record("session-1", "site-1", trial_input())
        second = service.record("session-1", "site-1", trial_input())
        report = service.report("session-1")
        assert not any(hasattr(service, name) for name in ("repository", "session", "connection", "engine"))
    assert first["trial_id"] != second["trial_id"]
    assert first["provenance"] == "agent-reported"
    assert first["current_source_status"] == "matches-session"
    assert [t["trial_id"] for t in report["trials"]] == [first["trial_id"], second["trial_id"]]
    assert report["outcome_counts"]["survived"] == 2
    assert report["unexplored_sites"] == []
    assert "content_base64" not in report["sources"][0]
    with mutation_store(database) as store:
        assert store.get_session("session-1") == ledger_session(root)


def test_reindexing_and_graph_deletion_preserve_mutation_history(ledger: tuple[Path, Path]) -> None:
    root, database = ledger
    with mutation_service(database) as service:
        trial = service.record("session-1", "site-1", trial_input())
    with repository_service(database) as service:
        service.save_folder(root, graph_artifact())
        service.save_folder(root, graph_artifact())
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("DELETE FROM repositories")
    with mutation_service(database) as service:
        report = service.report("session-1")
    assert report["trials"][0]["trial_id"] == trial["trial_id"]
    assert report["sites"][0]["site_id"] == "site-1"


def test_observed_source_state_is_independent_of_reported_restore(ledger: tuple[Path, Path]) -> None:
    root, database = ledger
    source = root / "payments.py"
    source.write_bytes(SOURCE + b"# pre-existing edit\n")
    with mutation_service(database) as service:
        acknowledgement = service.record("session-1", "site-1", trial_input())
        assert acknowledgement["current_source_status"] == "differs"
        assert acknowledgement["result"]["outcome"] == "survived"
        assert service.report("session-1")["sources"][0]["current_source_status"] == "differs"
        source.unlink()
        assert service.report("session-1")["sources"][0]["current_source_status"] == "missing"
        source.write_bytes(SOURCE)
        assert service.report("session-1")["sources"][0]["current_source_status"] == "matches-session"


def test_source_unreadable_or_unsafe_is_not_matching(ledger: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    root, _database = ledger
    source = ledger_session(root).sources[0]
    assert source_status(root, source.model_copy(update={"path": "../outside.py"})) == "unreadable"
    monkeypatch.setattr(Path, "read_bytes", lambda _self: (_ for _ in ()).throw(PermissionError()))
    assert source_status(root, source) == "unreadable"


def test_unknown_references_and_hash_mismatch_are_rejected(ledger: tuple[Path, Path]) -> None:
    _root, database = ledger
    with mutation_service(database) as service:
        with pytest.raises(RepositoryError, match="Unknown mutation session"):
            service.report("missing")
        with pytest.raises(RepositoryError, match="Unknown site"):
            service.record("session-1", "other-site", trial_input())
        with pytest.raises(ValueError, match="original_file_hash"):
            service.record("session-1", "site-1", trial_input("0" * 64))
        assert service.report("session-1")["trials"] == []


def test_duplicate_session_is_not_upserted(ledger: tuple[Path, Path]) -> None:
    root, database = ledger
    with pytest.raises(RepositoryError):
        with mutation_store(database) as store:
            store.save_session(ledger_session(root).model_copy(update={"sites": []}))
    with mutation_store(database) as store:
        assert store.get_session("session-1") == ledger_session(root)


def test_failed_site_insert_rolls_back_whole_session(ledger: tuple[Path, Path]) -> None:
    root, database = ledger
    session = ledger_session(root)
    broken = session.model_copy(update={"session_id": "broken", "sites": [session.sites[0], session.sites[0]]})
    with pytest.raises(RepositoryError):
        with mutation_store(database) as store:
            store.save_session(broken)
    with mutation_store(database) as store:
        with pytest.raises(RepositoryError, match="Unknown mutation session"):
            store.get_session("broken")
        assert store.get_session("session-1") == session
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM mutation_sources WHERE session_id='broken'").fetchone() == (0,)


def test_foreign_keys_reject_trial_for_another_session(ledger: tuple[Path, Path]) -> None:
    _root, database = ledger
    with pytest.raises(RepositoryError):
        with mutation_store(database) as store:
            store.append_trial(MutationTrial(
                trial_id="bad", session_id="missing", site_id="site-1", recorded_at="now", result=trial_input(),
            ))


def test_mutation_service_does_not_implicitly_migrate(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError, match="no such table"):
        with mutation_service(tmp_path / "unmigrated.sqlite") as service:
            service.report("missing")
