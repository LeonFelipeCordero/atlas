"""Index and report use the current directory unless a folder is supplied."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_text
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


@dataclass(frozen=True)
class FolderCase:
    command: str
    flag: str | None


@pytest.mark.parametrize("case", [
    pytest.param(FolderCase(command, flag), id=f"{command}-{flag or 'cwd'}")
    for command, flag in product(("index", "report"), (None, "-f", "--f", "--folder"))
])
def test_folder_default_and_aliases(
    case: FolderCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, flag = case.command, case.flag
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text(case_text('cli', 'folder-cli-folder-default-and-aliases', 'a.py'))
    (source / "b.py").write_text(case_text('cli', 'folder-cli-folder-default-and-aliases', 'b.py'))
    cwd = source if flag is None else tmp_path / "unrelated"
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)
    database = tmp_path / "central/db.sqlite"
    migrate_database(database)
    monkeypatch.setenv("DATABASE_PATH", str(database))
    arguments = [command]
    if flag is not None:
        arguments += [flag, str(source)]
    if command == "report":
        arguments += ["--save", "--format", "json"]
    result = CliRunner().invoke(main, arguments)
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 1
        project = projects[0]
        assert project.name == "source"
        assert project.location == str(source.resolve())
        saved = snapshot_result(service.get_architecture(project.id), 'get_architecture')
        assert saved is not None
        assert saved.stats.files == 2
        if command == "index":
            assert output["repositoryId"] == project.id
            assert output["stats"] == saved.stats.model_dump()
        else:
            assert output["summary"]["circularImportGroups"] == 1
    assert sorted(path.name for path in source.iterdir()) == ["a.py", "b.py"]


def test_report_default_cwd_without_saving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text(case_text('cli', 'folder-cli-report-default-cwd-without-saving', 'a.py'))
    (tmp_path / "b.py").write_text(case_text('cli', 'folder-cli-report-default-cwd-without-saving', 'b.py'))
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
