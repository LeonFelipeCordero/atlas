"""Report CLI analyzes folders freshly, saving only when requested."""

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.domain.repositories import RepositoryError


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    migrate_database(path)
    return path


def test_index_then_report_analyzes_fresh_folder(database: Path, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.py").write_text("import b\n")
    (root / "b.py").write_text("import a\n")
    (root / "app.py").write_text(
        "def high(value):\n"
        + "    if value: pass\n" * 8
        + "\ndef nested(items):\n"
        "    for item in items:\n"
        "        for child in item:\n"
        "            print(child)\n"
        "\ndef deep(value):\n"
        "    if value:\n"
        "        if value:\n"
        "            if value:\n"
        "                if value:\n"
        "                    return value\n"
        "\ndef simple():\n"
        "    return 1\n"
    )
    with repository_service(database) as service:
        registered = service.register({"name": "Example", "location": str(root)})
        other = service.register({"name": "Other", "location": str(root)})
    runner = CliRunner()
    indexed = runner.invoke(main, ["index", "-f", str(root)])
    assert indexed.exit_code == 0, indexed.output
    with repository_service(database) as service:
        original = service.get_architecture(registered.id)
    result = runner.invoke(main, ["report", "-f", str(root)])
    assert result.exit_code == 0, result.output
    assert "## Callables" in result.output
    assert "## Circular imports" in result.output
    assert "app.py:1" in result.output
    assert "Cyclomatic complexity" in result.output and "Weighted complexity" in result.output
    assert "Nested loops" in result.output and "Decision depth" in result.output
    assert "`a.py` → `b.py` → `a.py`" in result.output
    assert "limit" not in result.output
    assert "repositoryId" not in result.output
    structured = runner.invoke(main, ["report", "-f", str(root), "--format", "json"])
    assert structured.exit_code == 0, structured.output
    report = json.loads(structured.output)
    assert set(report) == {"summary", "nodes", "circularImports", "diagnostics"}
    complexity = {node["subject"].split("::")[-1]: node["metrics"] for node in report["nodes"] if node["kind"] == "function"}
    assert set(complexity) == {"high", "nested", "deep", "simple"}
    assert complexity["high"]["weightedComplexity"] == 9
    assert complexity["nested"]["nestedLoops"] == 1
    assert complexity["deep"]["maxDecisionDepth"] == 4
    assert complexity["simple"]["weightedComplexity"] == 1
    assert report["circularImports"][0]["files"] == ["a.py", "b.py"]
    assert report["summary"]["circularImportGroups"] == 1
    for source in root.iterdir():
        source.unlink()
    fresh = runner.invoke(main, ["report", "-f", str(root)])
    assert fresh.exit_code == 0, fresh.output
    assert "files: 0" in fresh.output and "circularImportGroups: 0" in fresh.output
    with repository_service(database) as service:
        assert service.get_architecture(registered.id) == original
        assert service.get_architecture(other.id) is None


def test_service_report_requires_project_name(database: Path) -> None:
    with repository_service(database) as service:
        with pytest.raises(RepositoryError, match="project name is required"):
            service.report(" ")


def test_report_empty_measurements_formats(database: Path, tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    result = CliRunner().invoke(main, ["report", "-f", str(root)])
    assert result.exit_code == 0, result.output
    assert "files: 0" in result.output
    structured = CliRunner().invoke(main, ["report", "-f", str(root), "--format", "json"])
    assert structured.exit_code == 0, structured.output
    assert json.loads(structured.output)["summary"]["files"] == 0
    assert json.loads(structured.output)["circularImports"] == []


@pytest.mark.parametrize("command", ["index", "report", "check"])
def test_saving_does_not_migrate_database(tmp_path: Path, command: str) -> None:
    root = tmp_path / "source"
    root.mkdir()
    database = tmp_path / "new.sqlite"
    args = [command, "-f", str(root)]
    if command != "index":
        args.append("--save")
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(main, args)
    assert result.exit_code == 1
    assert "no such table" in result.output
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []
