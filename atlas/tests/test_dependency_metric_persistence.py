"""Dependency metrics derive from complete persisted normalized report facts."""

from pathlib import Path
from typing import Any, cast

from sqlalchemy import event
from sqlalchemy.orm import Session

from atlas.bootstrap import repository_service
from atlas.domain.models import GraphView
from atlas.domain.repositories import ReportFactsDTO, ReportImportDTO
from atlas.metrics.artifact import build_dependency_views
from atlas.metrics.dependency_metrics import dependency_metrics
from atlas.persistence.database import create_engine, migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore
from tests.graph_storage_fixture import graph_artifact


def fact_views(facts: ReportFactsDTO) -> dict[str, dict[str, Any]]:
    return build_dependency_views(
        [node.model_dump() for node in facts.nodes],
        [edge.model_dump() for edge in facts.edges],
    )


def test_dependency_metrics_from_normalized_facts(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.py").write_text("import b\n")
    (root / "b.py").write_text("import a\n")
    (root / "c.py").write_text("import a\n")
    (root / "isolated.py").write_text("# no dependencies\n")
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    with repository_service(path) as service:
        repository = service.register({"name": "Metrics", "location": str(root)})
        graph = service.index(repository.name, root)
    with repository_service(path) as service:
        assert service.get_architecture(repository.id) == graph
        facts = service.repository.report_facts(repository.id)
        assert facts is not None
    metrics = dependency_metrics(cast(GraphView, fact_views(facts)["file"]))
    assert metrics["file:a.py"] == {
        "fanIn": 2, "fanOut": 1, "transitiveChangeImpact": 2, "instability": 1 / 3,
    }
    assert metrics["file:isolated.py"] == {
        "fanIn": 0, "fanOut": 0, "transitiveChangeImpact": 0, "instability": None,
    }
    assert facts.edges == facts.imports
    assert facts.diagnostics == []


def test_normalized_instability_excludes_duplicates_self_and_external_edges(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "stable.py").write_text("import unstable\nimport unstable\nimport stable\nimport missing\n")
    (root / "unstable.py").write_text("import a\nimport b\nimport c\nimport d\n")
    for peer in "abcd":
        (root / f"{peer}.py").write_text("import stable\n")
    (root / "isolated.py").write_text("# no dependencies\n")
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    with repository_service(path) as service:
        repository = service.register({"name": "Instability", "location": str(root)})
        service.index(repository.name, root)
        facts = service.repository.report_facts(repository.id)
        assert facts is not None
    metrics = dependency_metrics(cast(GraphView, fact_views(facts)["file"]))
    assert metrics["file:stable.py"] == {
        "fanIn": 4, "fanOut": 1, "transitiveChangeImpact": 5, "instability": 0.2,
    }
    assert metrics["file:unstable.py"] == {
        "fanIn": 1, "fanOut": 4, "transitiveChangeImpact": 5, "instability": 0.8,
    }
    assert metrics["file:isolated.py"]["instability"] is None
    assert len(facts.imports) == 12
    assert any(node.level == "external" for node in facts.nodes)


def rich_artifact() -> dict[str, Any]:
    artifact = graph_artifact()
    artifact["nodes"][0]["properties"].update(
        baseCyclomaticComplexity=3, nestedCyclomaticComplexity=2,
        loopNestedComplexity=1, cyclomaticComplexity=6, maxDecisionDepth=3,
    )
    edge = artifact["edges"][0]
    artifact["edges"].extend([
        {**edge, "type": "REFERENCES", "typeOnly": True, "evidence": None},
        {**edge, "type": "INHERITS", "path": None, "line": None, "evidence": None},
        {**edge, "type": "CONTAINS", "sourceStableKey": "file", "targetStableKey": "run"},
    ])
    return artifact


def test_normalized_facts_keep_all_dependency_occurrences_and_legacy_complexities(tmp_path: Path) -> None:
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    artifact = rich_artifact()
    with repository_session(path) as session:
        store = RepositoryStore(session)
        saved = store.save_new("Metrics", ".", artifact)
        facts = store.report_facts(saved.repositoryId)
        assert facts is not None
        assert facts.graphRevision == saved.graphRevision
    run, worker = facts.nodes[:2]
    assert (run.path, run.startLine, run.lineCount, run.parameterCount) == ("src/app.py", 1, 0, 0)
    assert (run.baseCyclomaticComplexity, run.nestedCyclomaticComplexity,
            run.loopNestedComplexity, run.cyclomaticComplexity, run.maxDecisionDepth) == (3, 2, 1, 6, 3)
    assert worker.baseCyclomaticComplexity is None
    assert worker.nestedCyclomaticComplexity is None
    assert facts.edges == [
        ReportImportDTO.model_validate({"typeOnly": False, **edge})
        for edge in artifact["edges"] if edge["type"] != "CONTAINS"
    ]
    assert facts.imports == [edge for edge in facts.edges if edge.type == "IMPORTS"]
    assert [edge.type for edge in facts.edges] == ["CALLS", "CALLS", "IMPORTS", "REFERENCES", "INHERITS"]
    assert facts.diagnostics == artifact["diagnostics"]
    metrics = dependency_metrics(cast(GraphView, fact_views(facts)["callable"]))
    assert metrics["run"] == {
        "fanIn": 0, "fanOut": 1, "transitiveChangeImpact": 0, "instability": 1.0,
    }
    assert metrics["worker"] == {
        "fanIn": 1, "fanOut": 0, "transitiveChangeImpact": 1, "instability": 0.0,
    }


def test_enriched_facts_share_a_revision_and_are_repository_scoped(tmp_path: Path) -> None:
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    original = rich_artifact()
    with repository_session(path) as session:
        store = RepositoryStore(session)
        saved = store.save_new("Metrics", ".", original)
        other = rich_artifact()
        other["diagnostics"][0]["message"] = "another repository"
        store.save_new("Other", ".", other)
    reader_engine, writer_engine = create_engine(path), create_engine(path)
    replacement = graph_artifact()
    replacement["edges"] = []
    replacement["diagnostics"] = []
    changed = False

    @event.listens_for(reader_engine, "before_cursor_execute")
    def replace_after_header(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal changed
        if changed or "FROM graph_nodes" not in statement:
            return
        changed = True
        with Session(writer_engine) as writer:
            RepositoryStore(writer).save(saved.repositoryId, replacement)

    try:
        with Session(reader_engine) as session:
            store = RepositoryStore(session)
            facts = store.report_facts(saved.repositoryId)
            assert changed and facts is not None
            assert facts.graphRevision == saved.graphRevision
            assert facts.nodes[0].baseCyclomaticComplexity == 3
            assert len(facts.edges) == 5
            assert len(facts.imports) == 1
            assert facts.diagnostics == original["diagnostics"]
            latest = store.report_facts(saved.repositoryId)
            assert latest is not None and latest.graphRevision != saved.graphRevision
            assert latest.edges == latest.imports == latest.diagnostics == []
    finally:
        reader_engine.dispose()
        writer_engine.dispose()


def test_report_facts_default_collections_are_independent() -> None:
    first = ReportFactsDTO(graphRevision="first", nodes=[], imports=[])
    second = ReportFactsDTO(graphRevision="second", nodes=[], imports=[])
    first.edges.append(ReportImportDTO(
        sourceStableKey="a", targetStableKey="b", type="CALLS", confidence="EXTRACTED",
        path=None, line=None, evidence=None, typeOnly=False,
    ))
    first.diagnostics.append({"message": "parse failed"})
    assert second.edges == second.diagnostics == []
