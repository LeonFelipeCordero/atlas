"""Index and report use the current directory unless a folder is supplied."""

import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from shutil import copytree

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT


@dataclass(frozen=True)
class FolderCase:
    command: str
    flag: str | None


def source_contents(source: Path) -> dict[Path, bytes]:
    return {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}


def folder_arguments(case: FolderCase, source: Path) -> list[str]:
    arguments = [case.command]
    if case.flag is not None:
        arguments += [case.flag, str(source)]
    if case.command == "report":
        arguments += ["--save", "--format", "json"]
    return arguments


def assert_saved_output(database: Path, source: Path, output: dict) -> None:
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 1
        project = projects[0]
        assert project.name == "source"
        assert project.location == str(source.resolve())
        saved = service.get_architecture(project.id)
        assert saved is not None
        assert saved.stats.files == len(list(source.rglob("*.py")))
        if "repositoryId" in output:
            assert output["repositoryId"] == project.id
            assert output["stats"] == saved.stats.model_dump()
        else:
            assert output["summary"]["circularImportGroups"] == 1
            assert output["circularImports"][0]["files"] == [
                "src/coffee/brewing/recipe.py", "src/coffee/reporting/report.py",
            ]


@pytest.mark.parametrize("case", [
    pytest.param(FolderCase(command, flag), id=f"{command}-{flag or 'cwd'}")
    for command, flag in product(("index", "report"), (None, "-f", "--f", "--folder"))
])
def test_folder_default_and_aliases(
    case: FolderCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = copytree(FIXTURE_ROOT / "python", tmp_path / "source")
    before = source_contents(source)
    cwd = source if case.flag is None else tmp_path / "unrelated"
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)
    database = tmp_path / "central/db.sqlite"
    migrate_database(database)
    monkeypatch.setenv("DATABASE_PATH", str(database))
    result = CliRunner().invoke(main, folder_arguments(case, source))
    assert result.exit_code == 0, result.output
    assert_saved_output(database, source, json.loads(result.output))
    assert source_contents(source) == before


def test_report_default_cwd_without_saving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    database = tmp_path / "missing/db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    result = CliRunner().invoke(main, ["report", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["summary"]["circularImportGroups"] == 1
    assert not database.parent.exists()


@pytest.mark.parametrize("command", ["report", "check"])
def test_skip_save_option_is_removed(command: str, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    help_result = runner.invoke(main, [command, "--help"])
    assert help_result.exit_code == 0
    assert "--save" in help_result.output
    assert "--skip-save" not in help_result.output
    rejected = runner.invoke(main, [command, "--skip-save"])
    assert rejected.exit_code == 2
    assert "No such option" in rejected.output and "--skip-save" in rejected.output
    assert not database.parent.exists()
