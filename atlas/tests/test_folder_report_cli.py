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
def test_folder_report_creates_and_updates_saved_project(
    source: Path, tmp_path: Path, flag: str,
) -> None:
    database = tmp_path / "central/db.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    args = ["report", flag, str(source), "--save", "--format", "json"]
    first = runner.invoke(main, args)
    assert first.exit_code == 0, first.output
    report = json.loads(first.output)
    assert report["summary"]["circularImportGroups"] == 1
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
    assert json.loads(updated.output)["summary"]["circularImportGroups"] == 0
    with repository_service(database) as service:
        assert [saved.id for saved in service.list()] == [project.id]
        assert service.get_architecture(project.id) != original
def test_folder_names_are_trimmed_for_registration(tmp_path: Path) -> None:
    source = tmp_path / " source "
    source.mkdir()
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    saved = runner.invoke(main, ["report", "-f", str(source), "--save"])
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        assert service.list()[0].name == "source"


def test_relative_folder_uses_user_database_not_source(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(source)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
    migrate_database()
    before = sorted(source.iterdir())
    result = CliRunner().invoke(main, ["report", "--f", "./", "--save"])
    assert result.exit_code == 0, result.output
    assert "## Circular imports" in result.output
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
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, ["report", "-f", str(source), "--save"])
    assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        assert len(service.list()) == 2
        assert service.get_architecture(registered.id) is not None
        assert service.get_architecture(other.id) is None


def test_same_basename_folders_get_distinct_projects(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    other = tmp_path / "other/EXAMPLE"
    other.mkdir(parents=True)
    for root in (source, other, source):
        result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, ["report", "-f", str(root), "--save"])
        assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        projects = service.list()
        assert {project.name for project in projects} == {"example", "EXAMPLE (2)"}
        assert {project.location for project in projects} == {str(source), str(other)}


@pytest.mark.parametrize("command", ["report", "check"])
def test_default_never_accesses_database(
    source: Path, monkeypatch: pytest.MonkeyPatch, command: str,
) -> None:
    from atlas import bootstrap

    def fail(*args: object) -> None:
        raise AssertionError("Database must not be accessed")

    monkeypatch.setattr(bootstrap, "repository_service", fail)
    monkeypatch.setattr(bootstrap, "migrate_database", fail)
    database = source.parent / "missing/db.sqlite"
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, [
        command, "-f", str(source), "--format", "json",
    ])
    assert result.exit_code == (0 if command == "report" else 1), result.output
    output = json.loads(result.output)
    if command == "report":
        assert output["circularImports"]
    else:
        assert output["findings"][0]["rule"] == "maxCircularImportGroups"
    assert not database.parent.exists()


@pytest.mark.parametrize("command", ["report", "check"])
def test_default_preserves_existing_graph(source: Path, tmp_path: Path, command: str) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    saved = runner.invoke(main, ["report", "-f", str(source), "--save"])
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        project = service.list()[0]
        original = service.get_architecture(project.id)
    (source / "b.py").write_text("value = 1\n")
    fresh = runner.invoke(main, [command, "-f", str(source)])
    assert fresh.exit_code == 0, fresh.output
    if command == "report":
        assert "circularImportGroups: 0" in fresh.output
        assert "## Circular imports" not in fresh.output
    else:
        assert fresh.output == "All checks passed.\n"
    with repository_service(database) as service:
        assert service.get_architecture(project.id) == original


@pytest.mark.parametrize("command", ["report", "check"])
def test_save_analyzes_once_and_keeps_output(
    source: Path, monkeypatch: pytest.MonkeyPatch, command: str,
) -> None:
    from atlas.services import repositories

    database = source.parent / "db.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    args = [command, "-f", str(source), "--format", "json"]
    calls: list[Path] = []
    analyze_folder = repositories.analyze_folder

    def analyze(root: Path):
        calls.append(root)
        return analyze_folder(root)

    monkeypatch.setattr(repositories, "analyze_folder", analyze)
    original = None
    for code in ("import a\n", "value = 1\n"):
        (source / "b.py").write_text(code)
        expected = runner.invoke(main, args)
        assert expected.exit_code == (1 if command == "check" and code == "import a\n" else 0), expected.output
        calls.clear()
        saved = runner.invoke(main, [*args, "--save"])
        assert saved.exit_code == expected.exit_code, saved.output
        assert saved.output == expected.output
        assert calls == [source.resolve()]
        with repository_service(database) as service:
            projects = service.list()
            assert len(projects) == 1
            graph = service.get_architecture(projects[0].id)
            assert graph is not None and graph != original
            assert graph.stats.files == 2
            original = graph


@pytest.mark.parametrize("args, message", [
    (["-f", "missing"], "Repository does not exist"),
])
def test_invalid_report_arguments_do_not_create_database(
    tmp_path: Path, args: list[str], message: str,
) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, ["report", *args])
    assert result.exit_code != 0
    assert message in result.output
    assert not database.parent.exists()


def test_file_is_not_a_report_folder(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, [
        "report", "-f", str(source / "a.py"),
    ])
    assert result.exit_code == 1
    assert "Repository does not exist" in result.output
    assert not database.parent.exists()


def test_global_project_selector_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, [
        "--project", "example", "report", "--f", ".",
    ])
    assert result.exit_code == 2
    assert "No such option" in result.output
    assert "--project" in result.output
    assert not database.parent.exists()


def test_failed_update_preserves_saved_graph(source: Path, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    args = ["report", "-f", str(source), "--save"]
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
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, ["report", "-f", str(source), "--save"])
    assert result.exit_code == 1
    assert "forced write failure" in result.output
    with repository_service(database) as service:
        assert service.list() == []
