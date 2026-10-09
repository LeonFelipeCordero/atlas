"""Report CLI analyzes folders freshly and supports database option placement."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.domain.repositories import RepositoryError


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "db.sqlite"
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
    indexed = runner.invoke(main, ["--database", str(database), "index", "-f", str(root)])
    assert indexed.exit_code == 0, indexed.output
    with repository_service(database) as service:
        original = service.get_architecture(registered.id)
    result = runner.invoke(main, ["report", "-f", str(root), "--database", str(database)])
    assert result.exit_code == 0, result.output
    assert "## Complexity:" in result.output
    assert "## Circular dependency:" in result.output
    assert "app.py:1" in result.output
    assert "Cyclomatic complexity is 9 (limit: 8)." in result.output
    assert "Nested-loop count is 1 (limit: 0)." in result.output
    assert "Decision nesting depth is 4 (limit: 3)." in result.output
    assert "a.py → b.py → a.py" in result.output
    assert "repositoryId" not in result.output
    local = runner.invoke(main, ["--database", str(database), "report", "-f", str(root)])
    assert local.exit_code == 0, local.output
    assert local.output == result.output
    structured = runner.invoke(main, [
        "report", "-f", str(root), "--database", str(database), "--format", "json",
    ])
    assert structured.exit_code == 0, structured.output
    report = json.loads(structured.output)
    assert set(report) == {"findings"}
    complexity = [finding for finding in report["findings"] if finding["type"] == "complexity"]
    assert {finding["subject"].split("::")[-1] for finding in complexity} == {"high", "nested", "deep"}
    assert all(finding["files"][0]["path"] == "app.py" for finding in complexity)
    group = report["findings"][-1]
    assert {file["path"] for file in group["files"]} == {"a.py", "b.py"}
    assert len(report["findings"]) == 4
    for source in root.iterdir():
        source.unlink()
    fresh = runner.invoke(main, ["report", "-f", str(root), "--database", str(database)])
    assert fresh.exit_code == 0, fresh.output
    assert fresh.output == "No findings.\n"
    with repository_service(database) as service:
        assert service.get_architecture(registered.id) != original
        assert service.get_architecture(other.id) is None


def test_service_report_requires_project_name(database: Path) -> None:
    with repository_service(database) as service:
        with pytest.raises(RepositoryError, match="project name is required"):
            service.report(" ")


def test_report_local_options_override_global_and_environment(database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "wrong.sqlite"))
    root = tmp_path / "empty"
    root.mkdir()
    result = CliRunner().invoke(main, [
        "--database", str(tmp_path / "wrong.sqlite"),
        "report", "-f", str(root), "--database", str(database),
    ])
    assert result.exit_code == 0, result.output
    assert result.output == "No findings.\n"
    structured = CliRunner().invoke(main, [
        "report", "-f", str(root), "--database", str(database), "--format", "json",
    ])
    assert structured.exit_code == 0, structured.output
    assert json.loads(structured.output) == {"findings": []}


def test_report_migrates_new_database(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    database = tmp_path / "new.sqlite"
    result = CliRunner().invoke(main, ["report", "-f", str(root), "--database", str(database)])
    assert result.exit_code == 0, result.output
    assert result.output == "No findings.\n"
    with repository_service(database) as service:
        assert service.get_architecture(service.list()[0].id) is not None
