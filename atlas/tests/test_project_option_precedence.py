"""Command-local project names override global selectors, including IDs."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


@pytest.mark.parametrize("command", ["index", "report"])
def test_local_project_name_overrides_global_id(command: str, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    with repository_service(database) as service:
        project = service.register({"name": "Local project", "location": str(tmp_path)})
        service.index(project.name, tmp_path)
    arguments = [command, str(tmp_path)] if command == "index" else [command, "--format", "json"]
    runner = CliRunner()
    options = ["--database", str(database), "--project"]
    selected = runner.invoke(main, options + [project.id] + arguments + ["--project", project.name])
    assert selected.exit_code == 0, selected.output
    result = json.loads(selected.output)
    if command == "index":
        assert result["repositoryId"] == project.id
    else:
        assert result == {"findings": []}
    rejected = runner.invoke(main, options + [project.name] + arguments + ["--project", project.id])
    assert rejected.exit_code == 1
    assert "Repository not found" in rejected.output
