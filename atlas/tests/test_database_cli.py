"""The CLI uses configured storage without accepting a database option."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli import main


@pytest.mark.parametrize("command", [None, "index", "projects", "report"])
def test_database_option_is_rejected(command: str | None, tmp_path: Path) -> None:
    database = tmp_path / "missing/db.sqlite"
    args = [command] if command else []
    result = CliRunner(env={"DATABASE_PATH": str(database)}).invoke(
        main, [*args, "--database", str(database)],
    )
    assert result.exit_code == 2
    assert "No such option" in result.output
    assert "--database" in result.output
    assert not database.parent.exists()


@pytest.mark.parametrize("command", [None, "index", "projects", "report"])
def test_help_has_no_database_option(command: str | None) -> None:
    result = CliRunner().invoke(main, [command, "--help"] if command else ["--help"])
    assert result.exit_code == 0
    assert "--database" not in result.output
