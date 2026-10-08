"""Normalized graph migration, SQL analysis and transactional replacement."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from atlas.bootstrap import repository_service
from atlas.indexer import analyze_repository
from atlas.persistence.database import create_engine, migrate_database
from atlas.persistence.normalized_schema import TABLES
from atlas.persistence.normalized import _property_values


def test_existing_artifacts_are_backfilled_and_downgrade_preserves_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_text("def run():\n    if True:\n        return 1\n")
    artifact = asdict(analyze_repository(root))
    path = tmp_path / "database.sqlite"
    engine = create_engine(path)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0001_initial")
            connection.exec_driver_sql(
                "INSERT INTO repositories VALUES ('legacy', 'Legacy', '.', 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO repository_graphs VALUES (?, ?, ?)",
                ("legacy", json.dumps(artifact), 42),
            )
        migrate_database(path)
        migrate_database(path)
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT count(*) FROM graph_nodes").fetchone()[0] == len(
                artifact["nodes"]
            )
            assert db.execute("SELECT count(*) FROM graph_edges").fetchone()[0] == len(
                artifact["edges"]
            )
            assert db.execute("SELECT count(*) FROM graph_node_ancestors").fetchone()[
                0
            ] == sum(len(node["ancestorStableKeys"]) for node in artifact["nodes"])
            assert (
                db.execute("""SELECT n.name, p.number_value FROM graph_nodes n
                JOIN graph_node_properties p ON p.repository_id=n.repository_id AND p.node_stable_key=n.stable_key
                WHERE p.name='cyclomaticComplexity' ORDER BY p.number_value DESC""").fetchall()
                == [("run", 2.0)]
            )
            assert (
                db.execute("""SELECT count(*) FROM graph_edges e
                JOIN graph_nodes source ON source.repository_id=e.repository_id AND source.stable_key=e.source_stable_key
                JOIN graph_nodes target ON target.repository_id=e.repository_id AND target.stable_key=e.target_stable_key""").fetchone()[
                    0
                ]
                == len(artifact["edges"])
            )
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with repository_service(path) as service:
            graph = service.get_architecture("legacy")
            assert graph is not None
            assert graph.artifact == artifact
            assert graph.importedAt == 42
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0001_initial")
            assert (
                json.loads(
                    connection.exec_driver_sql(
                        "SELECT artifact FROM repository_graphs"
                    ).scalar_one()
                )
                == artifact
            )
        migrate_database(path)
    finally:
        engine.dispose()


def test_views_cycles_and_property_values_are_queryable(tmp_path: Path) -> None:
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.py").write_text(
        "import b\n\n@staticmethod\ndef run():\n    return b.run()\n"
    )
    (root / "b.py").write_text("import a\n\ndef run():\n    return a.run()\n")
    with repository_service(path) as service:
        repository = service.register({"name": "Cycles", "location": str(root)})
        graph = service.index(repository.name, root)
    artifact = graph.artifact
    groups = artifact["circularDependencies"]["groups"]
    assert groups
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM graph_cycle_groups").fetchone()[
            0
        ] == len(groups)
        assert db.execute(
            "SELECT count(*) FROM graph_cycle_nodes WHERE role='member'"
        ).fetchone()[0] == sum(len(group["nodeStableKeys"]) for group in groups)
        assert db.execute("SELECT count(*) FROM graph_cycle_edges").fetchone()[
            0
        ] == sum(len(group["edges"]) for group in groups)
        assert db.execute(
            "SELECT text_value FROM graph_node_properties WHERE name='decorators' AND value_type='text'"
        ).fetchall() == [("@staticmethod",)]
        for level, view in artifact["views"].items():
            assert_persisted_view(db, level, view)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert_extension_property_values()


def assert_persisted_view(db, level, view) -> None:
    assert db.execute(
        "SELECT count(*) FROM graph_view_nodes WHERE level=?", (level,)
    ).fetchone()[0] == len(view["nodes"])
    assert db.execute(
        "SELECT count(*), coalesce(sum(count), 0) FROM graph_view_edges WHERE level=?",
        (level,),
    ).fetchone() == (
        len(view["edges"]),
        sum(edge["count"] for edge in view["edges"]),
    )
    for category in ("relationship", "confidence"):
        assert_persisted_view_counts(db, level, view, category)


def assert_persisted_view_counts(db, level, view, category) -> None:
    expected = sum(sum(edge[f"{category}Counts"].values()) for edge in view["edges"])
    assert db.execute(
        "SELECT coalesce(sum(count), 0) FROM graph_view_edge_counts WHERE level=? AND category=?",
        (level, category),
    ).fetchone() == (expected,)


def assert_extension_property_values() -> None:
    values = list(
        _property_values(
            "extension", {"a/b": 3, "flags": [True, False], "empty": [], "none": None}
        )
    )
    assert [
        (value["name"], value["position"], value["value_type"], value["number_value"])
        for value in values
    ] == [
        ("extension/a~1b", 0, "number", 3.0),
        ("extension/flags", 0, "boolean", 1.0),
        ("extension/flags", 1, "boolean", 0.0),
        ("extension/empty", 0, "array", None),
        ("extension/none", 0, "null", None),
    ]


def test_replacement_is_isolated_atomic_and_cascades(tmp_path: Path) -> None:
    path = tmp_path / "database.sqlite"
    migrate_database(path)
    root = tmp_path / "source"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def old():\n    return 1\n")
    with repository_service(path) as service:
        first = service.register({"name": "First", "location": str(root)})
        second = service.register({"name": "Second", "location": str(root)})
        service.index(first.name, root)
        original_second = service.index(second.name, root)
        source.write_text("def new():\n    return 2\n")
        replacement = service.index(first.name, root)
        assert service.get_architecture(second.id) == original_second
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT name FROM graph_nodes WHERE repository_id=? AND level='callable'",
            (first.id,),
        ).fetchall() == [("new",)]
        assert db.execute(
            "SELECT name FROM graph_nodes WHERE repository_id=? AND level='callable'",
            (second.id,),
        ).fetchall() == [("old",)]
        before = {
            table.name: db.execute(
                f"SELECT * FROM {table.name} ORDER BY 1, 2"
            ).fetchall()
            for table in TABLES
        }
        db.execute(
            "CREATE TRIGGER reject_node BEFORE INSERT ON graph_nodes BEGIN SELECT RAISE(ABORT, 'reject normalized write'); END"
        )
    with repository_service(path) as service:
        with pytest.raises(Exception, match="reject normalized write"):
            service.index(first.name, root)
        assert service.get_architecture(first.id) == replacement
    with sqlite3.connect(path) as db:
        assert before == {
            table.name: db.execute(
                f"SELECT * FROM {table.name} ORDER BY 1, 2"
            ).fetchall()
            for table in TABLES
        }
        db.execute("PRAGMA foreign_keys=ON")
        # Composite FKs prevent endpoints from referring to another repository.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO graph_edges VALUES (?, 999, 'missing', 'missing', 'CALLS', 'EXTRACTED', 'app.py', 1, NULL)",
                (first.id,),
            )
            db.commit()
        db.rollback()
        db.execute("DELETE FROM repositories WHERE id=?", (first.id,))
        for table in TABLES:
            assert db.execute(
                f"SELECT count(*) FROM {table.name} WHERE repository_id=?", (first.id,)
            ).fetchone() == (0,)
        assert (
            db.execute(
                "SELECT count(*) FROM graph_nodes WHERE repository_id=?", (second.id,)
            ).fetchone()[0]
            > 0
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
