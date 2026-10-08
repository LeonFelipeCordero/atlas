"""CLI reports must match the saved coffee sample output."""

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_report_matches_snapshot(language: str) -> None:
    result = CliRunner().invoke(main, [
        "report", "--folder", str(FIXTURE_ROOT / language), "--skip-save",
    ])
    assert result.exit_code == 0, result.output
    expected = (SNAPSHOT_ROOT / f"{language}-coffee-report.md").read_text(encoding="utf-8")
    assert result.output == expected
