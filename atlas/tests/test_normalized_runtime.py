"""Normalized-only reads, legacy reindexing, and repository response snapshots."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import event
from sqlalchemy.orm import Session

from atlas.bootstrap import repository_service
from atlas.domain.repositories import RepositoryError
from atlas.persistence.database import create_engine, migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore
from atlas.services.repositories import analyze_folder
from .graph_storage_fixture import graph_artifact, migration_config, normalized_rows


def test_legacy_graph_needs_reindex_and_keeps_registration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    engine = create_engine(path)
    with engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0003_graph_relations")
        connection.exec_driver_sql("INSERT INTO repositories VALUES ('legacy', 'Local', '.', 7)")
        connection.exec_driver_sql("INSERT INTO repository_graphs (repository_id, artifact, imported_at) VALUES ('legacy', 'invalid JSON', 9)")
    engine.dispose()
    migrate_database(path)
    with repository_service(path) as service:
        assert service.list()[0].id == "legacy"
        assert service.list()[0].importedAt is None
        assert service.get_architecture("legacy") is None
        with pytest.raises(RepositoryError, match="run atlas index"):
            service.report("Local")
        saved = service.index("Local", tmp_path)
        assert saved.repositoryId == "legacy"
        assert service.get_architecture("legacy") == saved
        assert service.report("Local") == {"findings": []}
    with sqlite3.connect(path) as connection:
        assert "artifact" not in [row[1] for row in connection.execute("PRAGMA table_info(repository_graphs)")]


def test_drop_downgrade_and_upgrade_preserve_normalized_rows(tmp_path: Path) -> None:
    path = tmp_path / "downgrade.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        identifier = RepositoryStore(session).save_new("Local", ".", graph_artifact()).repositoryId
    before = normalized_rows(path, identifier)
    engine = create_engine(path)
    with engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "0003_graph_relations")
        assert connection.exec_driver_sql("SELECT artifact FROM repository_graphs").scalar() == "{}"
    engine.dispose()
    migrate_database(path)
    assert normalized_rows(path, identifier) == before


@pytest.mark.parametrize("query", ["graph", "report_facts"])
def test_repository_multi_query_response_uses_one_revision(tmp_path: Path, query: str) -> None:
    path = tmp_path / "snapshot.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        original = RepositoryStore(session).save_new("Local", ".", graph_artifact())
    reader_engine = create_engine(path)
    writer_engine = create_engine(path)
    replacement = graph_artifact()
    replacement["nodes"][0]["properties"]["lineCount"] = 999
    replacement["nodes"] = replacement["nodes"][:-2] + [replacement["nodes"][-1]]
    replacement["edges"] = replacement["edges"][:2]
    changed = False

    @event.listens_for(reader_engine, "before_cursor_execute")
    def replace_after_header(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal changed
        if changed or "FROM graph_nodes" not in statement:
            return
        changed = True
        with Session(writer_engine) as writer:
            RepositoryStore(writer).save(original.repositoryId, replacement)

    try:
        with Session(reader_engine) as session:
            store = RepositoryStore(session)
            response = getattr(store, query)(original.repositoryId)
            assert changed
            assert response.graphRevision == original.graphRevision
            if query == "graph":
                assert response.stats == original.stats
            else:
                assert response.nodes[0].lineCount == 0
                assert len(response.nodes) == 5
                assert len(response.imports) == 1
            latest = store.graph(original.repositoryId)
            assert latest is not None and latest.graphRevision != original.graphRevision
    finally:
        reader_engine.dispose()
        writer_engine.dispose()


def test_report_facts_isolate_repositories_with_identical_node_keys(tmp_path: Path) -> None:
    path = tmp_path / "isolated-reports.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        store = RepositoryStore(session)
        first = store.save_new("First", ".", graph_artifact())
        expected = store.report_facts(first.repositoryId)
        assert expected is not None
        assert len(expected.nodes) == 5
        assert expected.nodes[0].lineCount == 0
        assert [edge.evidence for edge in expected.imports] == ["worker()"]
        other = graph_artifact()
        other["nodes"][0]["properties"]["lineCount"] = 777
        other["edges"][-1]["evidence"] = "other repository import"
        second = store.save_new("Second", ".", other)
        assert store.report_facts(first.repositoryId) == expected
        latest = store.report_facts(second.repositoryId)
        assert latest is not None
        assert len(latest.nodes) == 5
        assert latest.nodes[0].lineCount == 777
        assert [edge.evidence for edge in latest.imports] == ["other repository import"]
        assert store.graph(first.repositoryId) == first


def test_index_summary_counts_match_source_analysis(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested/app.py").write_text("import os\nclass App:\n    def run(self): return os.getcwd()\n")
    artifact = analyze_folder(root)
    path = tmp_path / "summary.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        saved = RepositoryStore(session).save_new("Local", str(root), artifact)
        assert saved.stats.model_dump() == artifact["stats"]


def test_failed_drop_rolls_back_revision_and_column(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "failed-drop.sqlite"
    engine = create_engine(path)
    with engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0003_graph_relations")
        connection.exec_driver_sql("INSERT INTO repositories VALUES ('legacy', 'Local', '.', 7)")
        connection.exec_driver_sql("INSERT INTO repository_graphs (repository_id, artifact, imported_at) VALUES ('legacy', 'invalid JSON', 9)")

    @event.listens_for(engine, "before_cursor_execute")
    def fail_after_drop(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("UPDATE alembic_version"):
            raise RuntimeError("forced revision failure")

    monkeypatch.setattr("atlas.persistence.database.create_engine", lambda _path: engine)
    with pytest.raises(RuntimeError, match="forced revision failure"):
        migrate_database(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_graph_relations",)
        assert connection.execute("SELECT artifact FROM repository_graphs").fetchone() == ("invalid JSON",)
        assert connection.execute("SELECT id FROM repositories").fetchone() == ("legacy",)
