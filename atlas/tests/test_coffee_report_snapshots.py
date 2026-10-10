"""CLI quantitative reports must match the saved coffee sample output."""

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
    assert "Cyclomatic complexity" in result.output and "Weighted complexity" in result.output
    assert "Decision depth" in result.output and "Parameters" in result.output
    assert "Internal instability" in result.output and "Change impact" in result.output
    if language != "go":
        assert "## Circular imports" in result.output
    assert "limit" not in result.output and "finding" not in result.output.lower()
    expected = (SNAPSHOT_ROOT / f"{language}-coffee-report.md").read_text(encoding="utf-8")
    assert result.output == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_size_measurements_include_every_source_and_callable(language: str) -> None:
    graph = coffee_graph(language)
    result = CliRunner().invoke(main, [
        "report", "--folder", str(FIXTURE_ROOT / language), "--skip-save", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    measurements = {node["stableKey"]: node for node in json.loads(result.output)["nodes"]}
    calibration = next(node for node in graph.nodes if node["name"] == "calibrate")
    assert_calibration_size(language, calibration, measurements)
    ready = next(node for node in graph.nodes if node["name"] == "ready")
    assert measurements[ready["stableKey"]]["metrics"]["parameterCount"] == 4
    assert set(measurements) >= {node["stableKey"] for node in graph.nodes if node["level"] == "file"}


def assert_calibration_size(language, calibration, measurements):
    path = calibration["path"]
    assert path is not None
    source = (FIXTURE_ROOT / language / path).read_bytes()
    assert "startLine" in calibration and "endLine" in calibration and "endColumn" in calibration
    end = calibration["endLine"] - int(calibration["endColumn"] == 1)
    file = measurements[f"file:{path}"]["metrics"]
    assert file["lineCount"] == len(source.splitlines()) and file["lineCount"] > 600
    metrics = measurements[calibration["stableKey"]]["metrics"]
    assert metrics["lineCount"] == end - calibration["startLine"] + 1
    assert metrics["lineCount"] > 100 and metrics["parameterCount"] == 8
    assert metrics["weightedComplexity"] == metrics["cyclomaticComplexity"] == 1
