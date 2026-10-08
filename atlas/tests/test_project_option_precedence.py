"""Saved report project names override global selectors, including IDs."""

import json
from pathlib import Path

from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


def test_local_report_project_name_overrides_global_id(tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    with repository_service(database) as service:
        project = service.register({"name": "Local project", "location": str(tmp_path)})
        service.index(project.name, tmp_path)
    runner = CliRunner()
    options = ["--database", str(database), "--project"]
    arguments = ["report", "--format", "json", "--project"]
    selected = runner.invoke(main, options + [project.id] + arguments + [project.name])
    assert selected.exit_code == 0, selected.output
    assert json.loads(selected.output) == {"findings": []}
    rejected = runner.invoke(main, options + [project.name] + arguments + [project.id])
    assert rejected.exit_code == 1
    assert "Repository not found" in rejected.output
