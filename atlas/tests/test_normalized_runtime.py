"""Normalized-only reads and repository response snapshots."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_text
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from atlas.persistence.database import create_engine, migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore
from atlas.services.repositories import analyze_folder
from .graph_storage_fixture import graph_artifact


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
    def replace_after_header(*cursor_event):
        nonlocal changed
        statement = cursor_event[2]
        if changed or "FROM graph_nodes" not in statement:
            return
        changed = True
        with Session(writer_engine) as writer:
            RepositoryStore(writer).save(original.repositoryId, replacement)

    try:
        with Session(reader_engine) as session:
            store = RepositoryStore(session)
            response = snapshot_result(getattr(store, query)(original.repositoryId), query)
            assert changed
            assert response.graphRevision == original.graphRevision
            if query == "graph":
                assert response.stats == original.stats
            else:
                assert response.nodes[0].lineCount == 0
                assert len(response.nodes) == 5
                assert len(response.imports) == 1
            latest = snapshot_result(store.graph(original.repositoryId), 'graph')
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
        expected = snapshot_result(store.report_facts(first.repositoryId), 'report_facts')
        assert expected is not None
        assert len(expected.nodes) == 5
        assert expected.nodes[0].lineCount == 0
        assert [edge.evidence for edge in expected.imports] == ["worker()"]
        other = graph_artifact()
        other["nodes"][0]["properties"]["lineCount"] = 777
        other["edges"][-1]["evidence"] = "other repository import"
        second = store.save_new("Second", ".", other)
        assert snapshot_result(store.report_facts(first.repositoryId), 'report_facts') == expected
        latest = snapshot_result(store.report_facts(second.repositoryId), 'report_facts')
        assert latest is not None
        assert len(latest.nodes) == 5
        assert latest.nodes[0].lineCount == 777
        assert [edge.evidence for edge in latest.imports] == ["other repository import"]
        assert snapshot_result(store.graph(first.repositoryId), 'graph') == first


def test_index_summary_counts_match_source_analysis(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested/app.py").write_text(case_text('cli', 'normalized-runtime-index-summary-counts-match-source-analysis', 'nested/app.py'))
    artifact = analyze_folder(root)
    path = tmp_path / "summary.sqlite"
    migrate_database(path)
    with repository_session(path) as session:
        saved = RepositoryStore(session).save_new("Local", str(root), artifact)
        assert saved.stats.model_dump() == artifact["stats"]
