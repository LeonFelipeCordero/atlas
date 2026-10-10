"""Dependency metrics derive from persisted normalized import facts."""

from pathlib import Path
from typing import cast

from atlas.bootstrap import repository_service
from atlas.domain.models import GraphView
from atlas.metrics.dependency_metrics import dependency_metrics
from atlas.persistence.database import migrate_database


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
        facts = service.get_report_facts(repository.id)
        assert facts is not None
    view = cast(GraphView, {
        "nodes": [node.stableKey for node in facts.nodes if node.level == "file"],
        "edges": [edge.model_dump() for edge in facts.imports],
    })
    metrics = dependency_metrics(view)
    assert metrics["file:a.py"]["transitiveChangeImpact"] == 2
    assert metrics["file:a.py"]["fanIn"] == 2
    assert metrics["file:isolated.py"]["fanOut"] == 0
