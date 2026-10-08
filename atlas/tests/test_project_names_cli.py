"""Saved report project selection is name-only, even for names resembling IDs."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main


@pytest.mark.parametrize("placement", ["global", "local"])
@pytest.mark.parametrize("name", [
    "Engineer's École $app",
    '$(exit 12) `exit 13` "$HOME"; exit 14',
    "line one\nline two",
    "--project",
])
def test_report_project_names_select_unambiguously(placement: str, name: str, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    root = tmp_path / "source"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def original():\n    return 1\n")
    with repository_service(database) as service:
        project = service.register({"name": name, "location": str(root)})
        baseline = service.index(project.name, root)
    runner = CliRunner()

    def invoke(name: str) -> Result:
        options = ["--project", name, "--database", str(database)]
        arguments = ["report", "--format", "json"]
        return runner.invoke(main, options + arguments if placement == "global" else arguments + options)

    # SQLite folds ASCII letters only, leaving non-ASCII characters unchanged.
    named = invoke(name.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")))
    assert named.exit_code == 0, named.output
    assert json.loads(named.output) == {"findings": []}
    with repository_service(database) as service:
        assert service.get_architecture(project.id) == baseline
    rejected = invoke(project.id)
    assert rejected.exit_code == 1
    assert "Repository not found" in rejected.output
    with repository_service(database) as service:
        assert service.get_architecture(project.id) == baseline
        other = service.register({"name": project.id, "location": str(root)})
    # Select the ID-named project, never fall back to the original graph.
    selected = invoke(project.id)
    assert selected.exit_code == 1
    assert "Repository has no indexed graph" in selected.output
    source.write_text("def high(value):\n" + "    if value: pass\n" * 8)
    with repository_service(database) as service:
        service.index(other.name, root)
    selected = invoke(project.id)
    assert selected.exit_code == 0, selected.output
    findings = json.loads(selected.output)["findings"]
    assert len(findings) == 1
    assert findings[0]["type"] == "complexity"
    assert findings[0]["subject"].endswith("::high")
    with repository_service(database) as service:
        assert service.get_architecture(other.id) is not None
        assert service.get_architecture(project.id) == baseline


def test_report_preserves_non_ascii_name_distinctions(tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    with repository_service(database) as service:
        upper = service.register({"name": "École", "location": str(tmp_path)})
        service.index(upper.name, tmp_path)
    runner = CliRunner()

    def invoke(name: str) -> Result:
        return runner.invoke(main, ["report", "--format", "json", "--database", str(database), "--project", name])

    assert invoke("ÉCOLE").exit_code == 0
    missing = invoke("école")
    assert missing.exit_code == 1
    assert "Repository not found" in missing.output
    with repository_service(database) as service:
        lower = service.register({"name": "école", "location": str(tmp_path)})
    unindexed = invoke("éCOLE")
    assert unindexed.exit_code == 1
    assert "Repository has no indexed graph" in unindexed.output
    with repository_service(database) as service:
        service.index(lower.name, tmp_path)
    selected = invoke("éCOLE")
    assert selected.exit_code == 0, selected.output
    with repository_service(database) as service:
        assert service.get_architecture(upper.id) is not None
        assert service.get_architecture(lower.id) is not None


@pytest.mark.parametrize("command", [None, "report"])
def test_help_describes_saved_report_project_names(command: str | None) -> None:
    result = CliRunner().invoke(main, [command, "--help"] if command else ["--help"])
    assert result.exit_code == 0
    assert "--project NAME" in result.output
    assert "Unique registered project name" in result.output
    assert "ID or" not in result.output
