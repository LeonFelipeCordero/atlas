"""Project listing emits JSON without requiring a project or changing graphs."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_text
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    migrate_database(path)
    return path


def test_projects_lists_indexed_and_unindexed_projects(database: Path, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_text(case_text('cli', 'projects-cli-projects-lists-indexed-and-unindexed-projects', 'app.py'))
    with repository_service(database) as service:
        indexed = service.register({"name": "École", "location": str(root)})
        unindexed = service.register({"name": "Other", "location": "elsewhere"})
        graph = service.index(indexed.name, root)
        expected = [project.model_dump(mode="json") for project in service.list()]
    result = CliRunner().invoke(main, ["projects"])
    assert result.exit_code == 0, result.output
    projects = json.loads(result.output)
    assert projects == expected
    assert {project["id"] for project in projects} == {indexed.id, unindexed.id}
    assert projects[0]["name"] == "École"
    assert projects[0]["location"] == str(root)
    assert projects[0]["createdAt"] > 0
    assert projects[0]["importedAt"] == graph.importedAt
    assert projects[1]["importedAt"] is None
    with repository_service(database) as service:
        assert snapshot_result(service.get_architecture(indexed.id), 'get_architecture') == graph
        assert snapshot_result(service.get_architecture(unindexed.id), 'get_architecture') is None


def test_projects_empty_database_is_empty_json_array(database: Path) -> None:
    result = CliRunner().invoke(main, ["projects"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_projects_unmigrated_database_has_cli_error(tmp_path: Path) -> None:
    result = CliRunner(env={"DATABASE_PATH": str(tmp_path / "new.sqlite")}).invoke(main, ["projects"])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "no such table" in result.output
