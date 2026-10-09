"""Removed project selectors and positional folders must be rejected."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli import main


@pytest.mark.parametrize("command", ["index", "report", "projects"])
def test_root_project_selector_is_rejected(command: str, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [
        "--project", "example", command, "--database", str(database),
    ])
    assert result.exit_code == 2
    assert "No such option" in result.output
    assert "--project" in result.output
    assert not database.parent.exists()


@pytest.mark.parametrize("command, flag", [
    ("index", "--project"),
    ("report", "-p"),
    ("report", "--p"),
    ("report", "--project"),
])
def test_command_project_selectors_are_rejected(command: str, flag: str, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [
        command, flag, "example", "--database", str(database),
    ])
    assert result.exit_code == 2
    assert "No such option" in result.output
    assert flag in result.output
    assert not database.parent.exists()


@pytest.mark.parametrize("command", ["index", "report"])
def test_positional_folder_is_rejected(command: str, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    result = CliRunner().invoke(main, [command, str(tmp_path), "--database", str(database)])
    assert result.exit_code == 2
    assert "unexpected extra argument" in result.output
    assert not database.parent.exists()


@pytest.mark.parametrize("command", [None, "index", "report"])
def test_help_has_no_project_selector(command: str | None) -> None:
    result = CliRunner().invoke(main, [command, "--help"] if command else ["--help"])
    assert result.exit_code == 0
    assert "--project" not in result.output
    if command:
        assert "-f, --f, --folder" in result.output
        assert "[default: .]" in result.output
