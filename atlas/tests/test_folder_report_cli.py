"""Folder reports analyze once, upsert centrally, or bypass storage entirely."""

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "example"
    root.mkdir()
    (root / "a.py").write_text("import b\n")
    (root / "b.py").write_text("import a\n")
    return root


@pytest.mark.parametrize("flag", ["-f", "--f", "--folder"])
def test_folder_report_creates_updates_and_reads_saved_project(
    source: Path, tmp_path: Path, flag: str,
) -> None:
    database = tmp_path / "central/db.sqlite"
    runner = CliRunner()
    args = ["report", flag, str(source), "--database", str(database), "--format", "json"]
    first = runner.invoke(main, args)
    assert first.exit_code == 0, first.output
    report = json.loads(first.output)
    assert report["findings"][0]["type"] == "circular_dependency"
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 1
        project = projects[0]
        assert project.name == "example"
        assert project.location == str(source.resolve())
        assert project.importedAt is not None
        original = service.get_architecture(project.id)
    (source / "b.py").write_text("value = 1\n")
    updated = runner.invoke(main, args)
    assert updated.exit_code == 0, updated.output
    assert json.loads(updated.output) == {"findings": []}
    with repository_service(database) as service:
        assert [saved.id for saved in service.list()] == [project.id]
        assert service.get_architecture(project.id) != original
    for file in source.iterdir():
        file.unlink()
    source.rmdir()
    for flag in ("-p", "--p", "--project"):
        saved = runner.invoke(main, ["report", flag, project.name, "--database", str(database)])
        assert saved.exit_code == 0, saved.output
        assert saved.output == "No findings.\n"


@pytest.mark.parametrize("flag", ["-p", "--p", "--project"])
def test_folder_project_aliases_preserve_name_only_lookup(
    source: Path, tmp_path: Path, flag: str,
) -> None:
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    saved = runner.invoke(main, ["report", "-f", str(source), "--database", str(database)])
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        project = service.list()[0]
    selected = runner.invoke(main, ["report", flag, "EXAMPLE", "--database", str(database)])
    assert selected.exit_code == 0, selected.output
    assert selected.output == saved.output
    rejected = runner.invoke(main, ["report", flag, project.id, "--database", str(database)])
    assert rejected.exit_code == 1
    assert "Repository not found" in rejected.output


def test_folder_names_are_trimmed_for_project_lookup(tmp_path: Path) -> None:
    source = tmp_path / " source "
    source.mkdir()
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    saved = runner.invoke(main, ["report", "-f", str(source), "--database", str(database)])
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        assert service.list()[0].name == "source"
    selected = runner.invoke(main, ["report", "-p", "source", "--database", str(database)])
    assert selected.exit_code == 0, selected.output
    assert selected.output == "No findings.\n"


def test_relative_folder_uses_user_database_not_source(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(source)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
    before = sorted(source.iterdir())
    result = CliRunner().invoke(main, ["report", "--f", "./"])
    assert result.exit_code == 0, result.output
    assert "Circular dependency" in result.output
    assert (tmp_path / "user-data/atlas/atlas.sqlite").exists()
    assert sorted(source.iterdir()) == before


def test_folder_updates_registered_location_not_same_name(
    source: Path, tmp_path: Path,
) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    with repository_service(database) as service:
        registered = service.register({"name": "Custom", "location": str(alias)})
        other = service.register({"name": "example", "location": str(tmp_path / "other")})
    result = CliRunner().invoke(main, ["report", "-f", str(source), "--database", str(database)])
    assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        assert len(service.list()) == 2
        assert service.get_architecture(registered.id) is not None
        assert service.get_architecture(other.id) is None


def test_same_basename_folders_get_distinct_projects(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    other = tmp_path / "other/EXAMPLE"
    other.mkdir(parents=True)
    for root in (source, other, source):
        result = CliRunner().invoke(main, ["report", "-f", str(root), "--database", str(database)])
        assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        projects = service.list()
        assert {project.name for project in projects} == {"example", "EXAMPLE (2)"}
        assert {project.location for project in projects} == {str(source), str(other)}


def test_skip_save_never_accesses_database(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from atlas import bootstrap

    def fail(*args: object) -> None:
        raise AssertionError("Database must not be accessed")

    monkeypatch.setattr(bootstrap, "repository_service", fail)
    monkeypatch.setattr(bootstrap, "migrate_database", fail)
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [
        "report", "-f", str(source), "--skip-save", "--database", str(database), "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["findings"]
    assert not database.parent.exists()


def test_skip_save_preserves_existing_graph(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    args = ["report", "-f", str(source), "--database", str(database)]
    saved = runner.invoke(main, args)
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        project = service.list()[0]
        original = service.get_architecture(project.id)
    (source / "b.py").write_text("value = 1\n")
    fresh = runner.invoke(main, [*args, "--skip-save"])
    assert fresh.exit_code == 0, fresh.output
    assert fresh.output == "No findings.\n"
    with repository_service(database) as service:
        assert service.get_architecture(project.id) == original


@pytest.mark.parametrize("args, message", [
    ([], "Provide either"),
    (["-f", ".", "-p", "example"], "not both"),
    (["--skip-save", "-p", "example"], "requires '--folder'"),
    (["-f", "missing"], "Repository does not exist"),
])
def test_invalid_report_arguments_do_not_create_database(
    tmp_path: Path, args: list[str], message: str,
) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, ["report", *args, "--database", str(database)])
    assert result.exit_code != 0
    assert message in result.output
    assert not database.parent.exists()


def test_file_is_not_a_report_folder(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [
        "report", "-f", str(source / "a.py"), "--database", str(database),
    ])
    assert result.exit_code == 1
    assert "Repository does not exist" in result.output
    assert not database.parent.exists()


def test_global_project_conflicts_with_folder(tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [
        "--project", "example", "report", "--f", ".", "--database", str(database),
    ])
    assert result.exit_code == 2
    assert "not both" in result.output
    assert not database.parent.exists()


def test_failed_update_preserves_saved_graph(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    args = ["report", "-f", str(source), "--database", str(database)]
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        project = service.list()[0]
        original = service.get_architecture(project.id)
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TRIGGER reject_update BEFORE UPDATE ON repository_graphs
            BEGIN SELECT RAISE(ABORT, 'forced update failure'); END""")
    (source / "b.py").write_text("value = 1\n")
    failed = runner.invoke(main, args)
    assert failed.exit_code == 1
    assert "forced update failure" in failed.output
    with repository_service(database) as service:
        assert len(service.list()) == 1
        assert service.get_architecture(project.id) == original


def test_failed_save_rolls_back_registration(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TRIGGER reject_graph BEFORE INSERT ON repository_graphs
            BEGIN SELECT RAISE(ABORT, 'forced write failure'); END""")
    result = CliRunner().invoke(main, ["report", "-f", str(source), "--database", str(database)])
    assert result.exit_code == 1
    assert "forced write failure" in result.output
    with repository_service(database) as service:
        assert service.list() == []
