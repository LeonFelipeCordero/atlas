"""CLI reports must match the saved coffee sample output."""

import json

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT, coffee_graph


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_report_matches_snapshot(language: str) -> None:
    result = CliRunner().invoke(main, [
        "report", "--folder", str(FIXTURE_ROOT / language), "--skip-save",
    ])
    assert result.exit_code == 0, result.output
    assert "Cyclomatic complexity is 9 (limit: 8)." in result.output
    assert "Decision nesting depth is 4 (limit: 3)." in result.output
    if language != "elixir":
        assert "Nested-loop count is 1 (limit: 0)." in result.output
    if language != "go":
        assert "## Circular dependency:" in result.output
    assert "File line count is " in result.output
    assert "Function line count is " in result.output
    assert "Parameter count is 8 (limit: 7)." in result.output
    expected = (SNAPSHOT_ROOT / f"{language}-coffee-report.md").read_text(encoding="utf-8")
    assert result.output == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_size_findings_identify_oversized_source_and_callable(language: str) -> None:
    graph = coffee_graph(language)
    calibration = next(node for node in graph.nodes if node["name"] == "calibrate")
    path = calibration["path"]
    assert path is not None
    file = next(node for node in graph.nodes if node["stableKey"] == f"file:{path}")
    source = (FIXTURE_ROOT / language / path).read_bytes()
    assert file["properties"]["lineCount"] == len(source.splitlines())
    assert file["properties"]["lineCount"] > 600
    assert "startLine" in calibration
    assert "endLine" in calibration
    assert "endColumn" in calibration
    end = calibration["endLine"] - int(calibration["endColumn"] == 1)
    assert calibration["properties"]["lineCount"] == end - calibration["startLine"] + 1
    assert calibration["properties"]["lineCount"] > 100
    assert calibration["properties"]["parameterCount"] == 8
    assert calibration["properties"]["cyclomaticComplexity"] == 1
    result = CliRunner().invoke(main, [
        "report", "--folder", str(FIXTURE_ROOT / language), "--skip-save", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    sizes = [finding for finding in json.loads(result.output)["findings"] if finding["type"] == "size"]
    assert len(sizes) == 2
    by_subject = {finding["subject"]: finding for finding in sizes}
    assert by_subject[file["qualifiedName"]] == {
        "type": "size", "subject": file["qualifiedName"], "files": [{"path": file["path"]}],
        "details": [f"File line count is {file['properties']['lineCount']} (limit: 600)."],
    }
    assert by_subject[calibration["qualifiedName"]] == {
        "type": "size", "subject": calibration["qualifiedName"],
        "files": [{"path": file["path"], "line": calibration["startLine"]}],
        "details": [
            f"Function line count is {calibration['properties']['lineCount']} (limit: 100).",
            "Parameter count is 8 (limit: 7).",
        ],
    }
