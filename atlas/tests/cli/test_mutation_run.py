"""Mutation execution CLI with real analysis, commands, and result files."""

import json
import sys
from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from atlas.cli import main
from atlas.persistence.database import migrate_database


@pytest.fixture
def project_factory(tmp_path):
    def create(rule="comparison.less-to-less-equal", command=None):
        (tmp_path / "src").mkdir()
        (tmp_path / "src/example.py").write_text("value = 1 < 2\n")
        settings = {"mutations": {
            "rules": [rule],
            "targets": {"unit": {
                "sources": ["src/**"],
                "command": command if command is not None else [sys.executable, "-c", "print('tested')"],
            }},
        }}
        (tmp_path / "atlas.json").write_text(json.dumps(settings))
        return tmp_path

    return create


@pytest.fixture
def project(project_factory):
    return project_factory()


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
    assert f"[mutations] Analyzing source files in {project}" in result.stderr
    assert "Planned 1 mutations: 1 mapped, 0 unmapped" in result.stderr
    assert "[1/1] src/example.py:1 comparison.less-to-less-equal: '<' -> '<='" in result.stderr
    assert result.stderr.index("Running target unit:") < result.stderr.index("Target unit: survived")
    assert "Source restored: src/example.py" in result.stderr
    assert 'Completed 1 mutations' in result.stderr
    record = json.loads(Path(summary["output"]).read_text())
    assert record["path"] == "src/example.py"
    assert Path(record["targets"][0]["log"]).read_text() == "tested\n"
    assert (project / "src/example.py").read_text() == "value = 1 < 2\n"


@pytest.mark.parametrize("saved", [False, True], ids=["fresh", "saved"])
def test_run_kills_mutation_with_real_tests(project_factory, monkeypatch, saved):
    root = project_factory(rule="comparison.less-to-greater", command=[sys.executable, "-m", "pytest", "-q", "tests"])
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_example.py").write_text(dedent("""
        from pathlib import Path
        import runpy

        def test_comparison():
            module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'src/example.py'))
            assert module['value'] is True
    """))
    source = root / "src/example.py"
    original = source.read_bytes()
    runner = CliRunner()
    if saved:
        database = root / "atlas.sqlite"
        monkeypatch.setenv("DATABASE_PATH", str(database))
        migrate_database(database)
        indexed = runner.invoke(main, ["index", "--folder", str(root)])
        assert indexed.exit_code == 0, indexed.output
    command = ["mutations", "--folder", str(root), *(["--saved"] if saved else []), "run"]
    no_refresh = patch("atlas.services.repositories.analyze_folder", side_effect=AssertionError("Saved mode must not reanalyze"))

    with no_refresh if saved else nullcontext():
        result = runner.invoke(main, command)

    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["counts"] == {"killed": 1}
    record = json.loads(Path(summary["output"]).read_text())
    execution = record["targets"][0]
    assert record["outcome"] == "killed"
    assert execution["exitCode"] == 1
    log = Path(execution["log"]).read_text()
    assert "FAILED tests/test_example.py::test_comparison" in log
    assert "assert False is True" in log
    assert source.read_bytes() == original
    phase = "Reading saved candidates" if saved else "Analyzing source files"
    assert phase in result.stderr
    assert "Target unit: killed (exit=1," in result.stderr


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
    assert "Completed" not in result.stderr


def test_rules_cannot_be_combined_with_run(project):
    result = CliRunner().invoke(main, ["mutations", "--rules", "run", "-f", str(project)])
    assert result.exit_code == 2
    assert "--rules cannot be combined" in result.stderr
