"""Dependency metrics persist generically without a schema migration."""

import sqlite3
from pathlib import Path

from atlas.bootstrap import repository_service
from atlas.domain.dependency_metrics import METRIC_NAMES
from atlas.persistence.database import migrate_database


def test_dependency_metrics_round_trip_in_snapshot_and_normalized_rows(
    tmp_path: Path,
) -> None:
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
        saved = service.get_architecture(repository.id)
        assert saved is not None
        assert saved.artifact == graph.artifact
    nodes = {node["stableKey"]: node for node in graph.artifact["nodes"]}
    assert nodes["file:a.py"]["properties"]["transitiveChangeImpact"] == 2
    assert nodes["file:a.py"]["properties"]["fanIn"] == 2
    assert nodes["file:isolated.py"]["properties"]["fanOut"] == 0
    expected = sorted(
        (key, name, float(node["properties"][name]))
        for key, node in nodes.items()
        if node["level"] in graph.artifact["views"]
        for name in METRIC_NAMES
    )
    with sqlite3.connect(path) as db:
        actual = db.execute(
            "SELECT node_stable_key, name, number_value FROM graph_node_properties "
            "WHERE repository_id=? AND name IN ('fanIn', 'fanOut', 'transitiveChangeImpact') "
            "ORDER BY node_stable_key, name",
            (repository.id,),
        ).fetchall()
        assert actual == expected
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
