"""Graph navigation selects the containing indexed folder without writing storage."""

import json
from itertools import product
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli.commands import main
from atlas.persistence.database import migrate_database, repository_session
from atlas.persistence.repositories import RepositoryStore
from tests.graph_storage_fixture import graph_artifact


@pytest.fixture
def indexed_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    database = tmp_path / "atlas.sqlite"
    root = tmp_path / "repo"
    (root / "src/nested").mkdir(parents=True)
    monkeypatch.setenv("DATABASE_PATH", str(database))
    migrate_database(database)
    with repository_session(database) as session:
        saved = RepositoryStore(session).save_new("Local", str(root), graph_artifact())
    return database, root, saved.repositoryId


@pytest.mark.parametrize("case", list(product([".", "src", "src/nested"], [
    ["overview"], ["find", "run"], ["show", "run"], ["children", "file"],
    ["context", "run"], ["source", "run"], ["path", "run", "worker"],
])))
def test_commands_infer_project(indexed_folder, monkeypatch, case) -> None:
    directory, args = case
    _, root, identifier = indexed_folder
    monkeypatch.chdir(root / directory)
    result = CliRunner().invoke(main, ["graph", *args])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["repositoryId"] == identifier


def test_nearest_indexed_folder_wins(indexed_folder, monkeypatch) -> None:
    database, root, _ = indexed_folder
    nested = root / "src"
    with repository_session(database) as session:
        saved = RepositoryStore(session).save_new("Nested", str(nested), graph_artifact())
    monkeypatch.chdir(nested / "nested")
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["repositoryId"] == saved.repositoryId


@pytest.mark.parametrize("directory", [".", "repo-other"])
def test_outside_folder_needs_explicit_project(indexed_folder, monkeypatch, directory) -> None:
    _, root, identifier = indexed_folder
    outside = root.parent / directory
    outside.mkdir(exist_ok=True)
    monkeypatch.chdir(outside)
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 1
    assert "No indexed project contains" in json.loads(result.stderr)["error"]
    explicit = CliRunner().invoke(main, ["graph", "--project", identifier, "overview"])
    assert explicit.exit_code == 0, explicit.output
    assert json.loads(explicit.output)["repositoryId"] == identifier


def test_duplicate_locations_need_explicit_project(indexed_folder, monkeypatch) -> None:
    database, root, identifier = indexed_folder
    with repository_session(database) as session:
        RepositoryStore(session).save_new("Duplicate", str(root / "src/.."), graph_artifact())
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 1
    assert "ambiguous" in json.loads(result.stderr)["error"]
    explicit = CliRunner().invoke(main, ["graph", "--project", identifier, "overview"])
    assert explicit.exit_code == 0, explicit.output


def test_location_symlink_is_canonicalized(indexed_folder, monkeypatch) -> None:
    database, root, identifier = indexed_folder
    alias = root.parent / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with repository_session(database) as session:
        from atlas.persistence.models import RepositoryRow

        row = session.get(RepositoryRow, identifier)
        assert row is not None
        row.location = str(alias)
        session.commit()
    monkeypatch.chdir(root / "src/nested")
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["repositoryId"] == identifier


def test_inference_does_not_create_missing_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "missing/atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 1
    assert "Cannot read graph database" in json.loads(result.stderr)["error"]
    assert not database.parent.exists()
