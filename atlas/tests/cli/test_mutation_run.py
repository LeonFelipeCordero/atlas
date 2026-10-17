"""Mutation execution CLI with real analysis, commands, and result files."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli import main


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/example.py").write_text("value = 1 < 2\n")
    settings = {"mutations": {
        "rules": ["comparison.less-to-less-equal"],
        "targets": {"unit": {"sources": ["src/**"], "command": [sys.executable, "-c", "print('tested')"]}},
    }}
    (tmp_path / "atlas.json").write_text(json.dumps(settings))
    return tmp_path


@pytest.mark.parametrize("args", [
    ["mutations", "run", "--folder"], ["mutations", "--folder"],
])
def test_run_accepts_project_folder_and_writes_results(project, args):
    command = [*args, str(project)]
    if args[-1] == "--folder" and "run" not in args:
        command.append("run")
    result = CliRunner().invoke(main, command)
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["counts"] == {"survived": 1}
    record = json.loads(Path(summary["output"]).read_text())
    assert record["path"] == "src/example.py"
    assert Path(record["targets"][0]["log"]).read_text() == "tested\n"
    assert (project / "src/example.py").read_text() == "value = 1 < 2\n"


def test_run_requires_targets_before_analysis(tmp_path):
    result = CliRunner().invoke(main, ["mutations", "run", "-f", str(tmp_path)])
    assert result.exit_code == 1
    assert "Configure mutations.targets" in result.stderr
    assert not (tmp_path / "mutation-results.jsonl").exists()


def test_custom_output_and_existing_results_are_protected(project):
    args = ["mutations", "run", "-f", str(project), "--output", "custom.jsonl"]
    assert CliRunner().invoke(main, args).exit_code == 0
    original = (project / "custom.jsonl").read_bytes()
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 1
    assert (project / "custom.jsonl").read_bytes() == original


def test_rules_cannot_be_combined_with_run(project):
    result = CliRunner().invoke(main, ["mutations", "--rules", "run", "-f", str(project)])
    assert result.exit_code == 2
    assert "--rules cannot be combined" in result.stderr
