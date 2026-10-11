"""CLI checks must match the saved coffee sample Markdown output."""

import json

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_check_matches_snapshot(language: str) -> None:
    result = CliRunner().invoke(main, [
        "check", "--folder", str(FIXTURE_ROOT / language),
    ])
    findings = CliRunner().invoke(main, [
        "check", "--folder", str(FIXTURE_ROOT / language), "--format", "json",
    ])
    expected_exit = int(bool(json.loads(findings.output)["findings"]))
    assert findings.exit_code == result.exit_code == expected_exit, result.output
    expected = (SNAPSHOT_ROOT / f"{language}-coffee-check.md").read_text(encoding="utf-8")
    assert result.output == expected
