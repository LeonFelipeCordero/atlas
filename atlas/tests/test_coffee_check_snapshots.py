"""CLI checks must match the saved coffee sample Markdown output."""

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_check_matches_snapshot(language: str) -> None:
    result = CliRunner().invoke(main, [
        "check", "--folder", str(FIXTURE_ROOT / language),
    ])
    assert result.exit_code == 1, result.output
    expected = (SNAPSHOT_ROOT / f"{language}-coffee-check.md").read_text(encoding="utf-8")
    assert result.output == expected
