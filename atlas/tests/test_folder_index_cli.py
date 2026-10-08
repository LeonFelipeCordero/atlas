"""Index selects a folder, migrates storage and upserts without project names."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import repository_service
from atlas.cli import main


@pytest.mark.parametrize("flag", ["-f", "--f", "--folder"])
def test_index_creates_and_updates_project(tmp_path: Path, flag: str) -> None:
    source = tmp_path / "example"
    source.mkdir()
    file = source / "main.py"
    file.write_text("def original():\n    return 1\n")
    database = tmp_path / "central/db.sqlite"
    runner = CliRunner()
    args = ["index", flag, str(source), "--database", str(database)]
    first = runner.invoke(main, args)
    assert first.exit_code == 0, first.output
    summary = json.loads(first.output)
    assert set(summary) == {"repositoryId", "schemaVersion", "stats"}
    assert summary["schemaVersion"] == 2
    assert summary["stats"]["files"] == 1
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 1
        project = projects[0]
        assert summary["repositoryId"] == project.id
        assert project.name == "example"
        assert project.location == str(source.resolve())
        assert project.importedAt is not None
        original = service.get_architecture(project.id)
        assert original is not None
        assert original.artifact["stats"] == summary["stats"]
    file.write_text("def replacement():\n    return 2\n")
    updated = runner.invoke(main, args)
    assert updated.exit_code == 0, updated.output
    assert json.loads(updated.output)["repositoryId"] == project.id
    with repository_service(database) as service:
        assert [saved.id for saved in service.list()] == [project.id]
        graph = service.get_architecture(project.id)
        assert graph is not None
        names = {node["name"] for node in graph.artifact["nodes"]}
        assert "replacement" in names and "original" not in names
    report = runner.invoke(main, ["report", "-p", project.name, "--database", str(database)])
    assert report.exit_code == 0, report.output
    assert report.output == "No findings.\n"


def test_index_expands_home_and_local_database_overrides_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    database = tmp_path / "correct.sqlite"
    wrong = tmp_path / "wrong.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(wrong))
    result = CliRunner().invoke(main, [
        "--database", str(wrong), "index", "-f", "~/source", "--database", str(database),
    ])
    assert result.exit_code == 0, result.output
    assert not wrong.exists()
    with repository_service(database) as service:
        assert service.list()[0].location == str(source)


def test_index_and_folder_report_share_project(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    file = source / "main.py"
    file.write_text("def original(): pass\n")
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    args = ["-f", str(source), "--database", str(database)]
    report = runner.invoke(main, ["report", *args])
    assert report.exit_code == 0, report.output
    with repository_service(database) as service:
        project = service.list()[0]
    file.write_text("def replacement(): pass\n")
    indexed = runner.invoke(main, ["index", *args])
    assert indexed.exit_code == 0, indexed.output
    assert json.loads(indexed.output)["repositoryId"] == project.id
    report = runner.invoke(main, ["report", *args])
    assert report.exit_code == 0, report.output
    with repository_service(database) as service:
        assert [saved.id for saved in service.list()] == [project.id]


def test_index_analyzes_once_before_saving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas.services import repositories

    source = tmp_path / "source"
    source.mkdir()
    database = tmp_path / "central/db.sqlite"
    analyze = repositories.analyze_folder
    analyzed = []

    def track(root: Path) -> dict:
        assert not database.parent.exists()
        analyzed.append(root)
        return analyze(root)

    monkeypatch.setattr(repositories, "analyze_folder", track)
    result = CliRunner().invoke(main, ["index", "-f", str(source), "--database", str(database)])
    assert result.exit_code == 0, result.output
    assert analyzed == [source.resolve()]


@pytest.mark.parametrize("args, message", [
    (["index"], "Missing option '-f'"),
    (["index", "-f"], "requires an argument"),
    (["index", "-f", "missing"], "Repository does not exist"),
    (["index", ".", "-f", "."], "unexpected extra argument"),
    (["index", "-f", ".", "--project", "example"], "No such option '--project'"),
    (["--project", "example", "index", "-f", "."], "only supported for saved reports"),
])
def test_invalid_index_arguments_do_not_create_database(
    tmp_path: Path, args: list[str], message: str,
) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, ["--database", str(database), *args])
    assert result.exit_code != 0
    assert message in result.output
    assert not database.parent.exists()


def test_failed_index_analysis_preserves_saved_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas.services import repositories

    source = tmp_path / "source"
    source.mkdir()
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    args = ["index", "-f", str(source), "--database", str(database)]
    saved = runner.invoke(main, args)
    assert saved.exit_code == 0, saved.output
    with repository_service(database) as service:
        project = service.list()[0]
        original = service.get_architecture(project.id)

    def fail(root: Path) -> dict:
        raise ValueError("forced analysis failure")

    monkeypatch.setattr(repositories, "analyze_folder", fail)
    failed = runner.invoke(main, args)
    assert failed.exit_code == 1
    assert "forced analysis failure" in failed.output
    with repository_service(database) as service:
        assert [saved.id for saved in service.list()] == [project.id]
        assert service.get_architecture(project.id) == original


@pytest.mark.parametrize("command", ["index", "report"])
def test_ambiguous_folder_does_not_change_either_project(tmp_path: Path, command: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    file = source / "main.py"
    file.write_text("def original(): pass\n")
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    migrated = runner.invoke(main, ["migrate", "--database", str(database)])
    assert migrated.exit_code == 0, migrated.output
    with repository_service(database) as service:
        first = service.register({"name": "First", "location": str(source)})
        second = service.register({"name": "Second", "location": str(alias)})
        first_graph = service.index(first.name, source)
        second_graph = service.index(second.name, source)
    file.write_text("def replacement(): pass\n")
    result = runner.invoke(main, [command, "-f", str(source), "--database", str(database)])
    assert result.exit_code == 1
    assert "Multiple projects are registered for this folder" in result.output
    with repository_service(database) as service:
        assert len(service.list()) == 2
        assert service.get_architecture(first.id) == first_graph
        assert service.get_architecture(second.id) == second_graph


@pytest.mark.parametrize("command", ["index", "report"])
@pytest.mark.parametrize("legacy", [False, True])
def test_relative_registration_never_follows_index_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, legacy: bool,
) -> None:
    source = tmp_path / "first"
    other = tmp_path / "second"
    source.mkdir()
    other.mkdir()
    (source / "main.py").write_text("def first(): pass\n")
    (other / "main.py").write_text("def second(): pass\n")
    database = tmp_path / "db.sqlite"
    runner = CliRunner()
    migrated = runner.invoke(main, ["migrate", "--database", str(database)])
    assert migrated.exit_code == 0, migrated.output
    monkeypatch.chdir(source)
    with repository_service(database) as service:
        project = (
            service.repository.register("First", ".")
            if legacy else service.register({"name": "First", "location": "."})
        )
        assert project.location == ("." if legacy else str(source))
        original = service.index(project.name, source)
    monkeypatch.chdir(other)
    result = runner.invoke(main, [command, "-f", "./", "--database", str(database)])
    assert result.exit_code == 0, result.output
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 2
        second = next(saved for saved in projects if saved.id != project.id)
        assert second.location == str(other)
        assert service.get_architecture(project.id) == original
        graph = service.get_architecture(second.id)
        assert graph is not None
        assert "second" in {node["name"] for node in graph.artifact["nodes"]}
