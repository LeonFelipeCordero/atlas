"""Index and report use the current directory unless a folder is supplied."""

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
    FolderCase(command, flag)
    for command, flag in product(("index", "report"), (None, "-f", "--f", "--folder"))
])
def test_folder_default_and_aliases(
    case: FolderCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, flag = case.command, case.flag
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("import b\n")
    (source / "b.py").write_text("import a\n")
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
        arguments += ["--format", "json"]
    result = CliRunner().invoke(main, arguments)
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    with repository_service(database) as service:
        projects = service.list()
        assert len(projects) == 1
        project = projects[0]
        assert project.name == "source"
        assert project.location == str(source.resolve())
        saved = service.get_architecture(project.id)
        assert saved is not None
        assert saved.stats.files == 2
        if command == "index":
            assert output["repositoryId"] == project.id
            assert output["stats"] == saved.stats.model_dump()
        else:
            assert output["summary"]["circularImportGroups"] == 1
    assert sorted(path.name for path in source.iterdir()) == ["a.py", "b.py"]


def test_report_default_cwd_skip_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("import b\n")
    (tmp_path / "b.py").write_text("import a\n")
    database = tmp_path / "missing/db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    result = CliRunner().invoke(main, ["report", "--skip-save", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["summary"]["circularImportGroups"] == 1
    assert not database.parent.exists()
