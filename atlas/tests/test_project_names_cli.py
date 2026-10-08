"""CLI project selection is name-only, even when a name resembles an ID."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.domain.repositories import GraphDTO


def _assert_named_graph(command: str, graph: GraphDTO, baseline: GraphDTO) -> None:
    if command != "index":
        assert graph == baseline
        return
    names = {node["name"] for node in graph.artifact["nodes"]}
    assert "replacement" in names and "original" not in names


@pytest.mark.parametrize("command", ["index", "report"])
@pytest.mark.parametrize("placement", ["global", "local"])
@pytest.mark.parametrize("name", [
    "Engineer's École $app",
    '$(exit 12) `exit 13` "$HOME"; exit 14',
    "line one\nline two",
    "--project",
])
def test_project_names_select_unambiguously(command: str, placement: str, name: str, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    root = tmp_path / "source"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def original():\n    return 1\n")
    with repository_service(database) as service:
        project = service.register({"name": name, "location": str(root)})
        baseline = service.index(project.name, root)
    if command == "index":
        source.write_text("def replacement():\n    return 2\n")
    runner = CliRunner()

    def invoke(name: str) -> Result:
        options = ["--project", name, "--database", str(database)]
        arguments = [command, str(root)] if command == "index" else [command, "--format", "json"]
        return runner.invoke(main, options + arguments if placement == "global" else arguments + options)

    # SQLite folds ASCII letters only, leaving non-ASCII characters unchanged.
    named = invoke(name.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")))
    assert named.exit_code == 0, named.output
    if command == "index":
        assert json.loads(named.output)["repositoryId"] == project.id
    else:
        assert json.loads(named.output) == {"findings": []}
    with repository_service(database) as service:
        original = service.get_architecture(project.id)
        assert original is not None
        _assert_named_graph(command, original, baseline)
    source.write_text("def id_named():\n    return 3\n")
    rejected = invoke(project.id)
    assert rejected.exit_code == 1
    assert "Repository not found" in rejected.output
    with repository_service(database) as service:
        saved = service.get_architecture(project.id)
        assert saved == original
        other = service.register({"name": project.id, "location": str(root)})
        # Leave the ID-named project unindexed: report must select it, not
        # silently fall back to the original project's indexed graph.
    if command == "report":
        selected = invoke(project.id)
        assert selected.exit_code == 1
        assert "Repository has no indexed graph" in selected.output
        source.write_text("def high(value):\n" + "    if value: pass\n" * 8)
        with repository_service(database) as service:
            service.index(other.name, root)
    selected = invoke(project.id)
    assert selected.exit_code == 0, selected.output
    if command == "index":
        assert json.loads(selected.output)["repositoryId"] == other.id
    else:
        findings = json.loads(selected.output)["findings"]
        assert len(findings) == 1
        assert findings[0]["type"] == "complexity"
        assert findings[0]["subject"].endswith("::high")
    with repository_service(database) as service:
        other_graph = service.get_architecture(other.id)
        assert other_graph is not None
        if command == "index":
            assert "id_named" in {node["name"] for node in other_graph.artifact["nodes"]}
        saved = service.get_architecture(project.id)
        assert saved == original


@pytest.mark.parametrize("command", ["index", "report"])
def test_cli_preserves_non_ascii_name_distinctions(command: str, tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite"
    migrate_database(database)
    with repository_service(database) as service:
        upper = service.register({"name": "École", "location": str(tmp_path)})
        service.index(upper.name, tmp_path)
    arguments = [command, str(tmp_path)] if command == "index" else [command, "--format", "json"]
    runner = CliRunner()

    def invoke(name: str) -> Result:
        return runner.invoke(main, arguments + ["--database", str(database), "--project", name])

    assert invoke("ÉCOLE").exit_code == 0
    missing = invoke("école")
    assert missing.exit_code == 1
    assert "Repository not found" in missing.output
    with repository_service(database) as service:
        lower = service.register({"name": "école", "location": str(tmp_path)})
    if command == "report":
        unindexed = invoke("éCOLE")
        assert unindexed.exit_code == 1
        assert "Repository has no indexed graph" in unindexed.output
        with repository_service(database) as service:
            service.index(lower.name, tmp_path)
    selected = invoke("éCOLE")
    assert selected.exit_code == 0, selected.output
    if command == "index":
        assert json.loads(selected.output)["repositoryId"] == lower.id
    with repository_service(database) as service:
        assert service.get_architecture(upper.id) is not None
        assert service.get_architecture(lower.id) is not None


@pytest.mark.parametrize("command", [None, "index", "report"])
def test_help_describes_project_names(command: str | None) -> None:
    result = CliRunner().invoke(main, [command, "--help"] if command else ["--help"])
    assert result.exit_code == 0
    assert "--project NAME" in result.output
    assert "Unique registered project name" in result.output
    assert "ID or" not in result.output
