"""Mutation execution CLI with real analysis, commands, and result files."""

import json
import sys
from io import BytesIO
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
    def create(rule="comparison.less-to-less-equal", command=None, targets=None):
        (tmp_path / "src").mkdir()
        (tmp_path / "src/example.py").write_text("value = 1 < 2\n")
        settings = {"mutations": {
            "rules": [rule],
            "targets": targets if targets is not None else {"unit": {
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
    result = CliRunner().invoke(main, [*command, "--target", "unit"])
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
    command = ["mutations", "--folder", str(root), *(["--saved"] if saved else []), "run", "--target", "all"]
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


@pytest.fixture
def target_project(project_factory):
    sources = {"unit": ["src/example.py"], "other": ["src/other.py"], "shared": ["src/*.py"]}
    targets = {name: {"sources": patterns, "command": [sys.executable, "-c",
               f"from pathlib import Path; Path('{name}.executed').touch()"]} for name, patterns in sources.items()}
    root = project_factory(targets=targets)
    (root / "src/other.py").write_text("value = 1 < 2\n")
    (root / "outside.py").write_text("untouched = 1 < 2\n")
    return root


@pytest.mark.parametrize("case", [
    ("unit", {"src/example.py": ["unit"]}, {"unit"}),
    ("other", {"src/other.py": ["other"]}, {"other"}),
    (" other, unit,unit ", {"src/example.py": ["unit"], "src/other.py": ["other"]}, {"unit", "other"}),
    ("all", {"src/example.py": ["unit", "shared"], "src/other.py": ["other", "shared"]}, {"unit", "other", "shared"}),
])
def test_explicit_targets_filter_sources_and_commands(target_project, case):
    selection, expected, executed = case
    original = {path: path.read_bytes() for path in target_project.rglob("*.py")}

    result = CliRunner().invoke(main, ["mutations", "run", "-f", str(target_project), "--target", selection])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["counts"] == {"survived": len(expected)}
    records = _result_records(target_project)
    assert {record["path"]: _target_names(record) for record in records} == expected
    assert {path.stem for path in target_project.glob("*.executed")} == executed
    assert {path: path.read_bytes() for path in original} == original
    assert "Available mutation targets:" not in result.stderr


def test_saved_selection_ignores_stale_unselected_sources(target_project, monkeypatch):
    database = target_project / "atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    migrate_database(database)
    runner = CliRunner()
    indexed = runner.invoke(main, ["index", "--folder", str(target_project)])
    assert indexed.exit_code == 0, indexed.output
    unselected = target_project / "src/other.py"
    unselected.write_text("user_edit = 3 < 4\n")

    result = runner.invoke(main, ["mutations", "--saved", "--folder", str(target_project), "run", "--target", "unit"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["counts"] == {"survived": 1}
    assert _result_records(target_project)[0]["path"] == "src/example.py"
    assert unselected.read_text() == "user_edit = 3 < 4\n"
    assert {path.stem for path in target_project.glob("*.executed")} == {"unit"}


class TerminalInput(BytesIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("case", [
    ("unit\n", {"src/example.py": ["unit"]}),
    ("unit,other\n", {"src/example.py": ["unit"], "src/other.py": ["other"]}),
    ("all\n", {"src/example.py": ["unit", "shared"], "src/other.py": ["other", "shared"]}),
    ("unknown\nother\n", {"src/other.py": ["other"]}),
    ("all,unit\nunit\n", {"src/example.py": ["unit"]}),
])
def test_interactive_target_selection(target_project, case):
    answer, expected = case

    result = CliRunner().invoke(main, ["mutations", "run", "-f", str(target_project)], input=TerminalInput(answer.encode()))

    assert result.exit_code == 0, result.output
    assert "Available mutation targets:" in result.stderr
    assert "all (all configured targets)" in result.stderr
    assert "  shared" in result.stderr
    assert json.loads(result.stdout)["counts"] == {"survived": len(expected)}
    assert {record["path"]: _target_names(record) for record in _result_records(target_project)} == expected


@pytest.mark.parametrize("selection", ["missing", "unit,missing", "all,unit", "", "unit,", ",", " , "])
def test_invalid_target_selection_fails_before_analysis(target_project, selection):
    with patch("atlas.services.repositories.analyze_folder", side_effect=AssertionError("Must validate before analysis")):
        result = CliRunner().invoke(main, ["mutations", "run", "-f", str(target_project), "--target", selection])
    assert result.exit_code == 2, result.output
    assert "Invalid value for --target:" in result.stderr
    assert not (target_project / "mutation-results.jsonl").exists()
    assert not list(target_project.glob("*.executed"))


def test_noninteractive_run_requires_explicit_targets(target_project):
    with patch("atlas.services.repositories.analyze_folder", side_effect=AssertionError("Must validate before analysis")):
        result = CliRunner().invoke(main, ["mutations", "run", "-f", str(target_project)], input="unit\n")
    assert result.exit_code == 2
    assert "Pass --target NAME[,NAME...] or --target all" in result.stderr
    assert "Available mutation targets:" not in result.stderr
    assert not (target_project / "mutation-results.jsonl").exists()


def test_interactive_eof_does_not_start_a_run(target_project):
    result = CliRunner().invoke(main, ["mutations", "run", "-f", str(target_project)], input=TerminalInput())
    assert result.exit_code == 1
    assert "Aborted!" in result.stderr
    assert not (target_project / "mutation-results.jsonl").exists()


def _result_records(root):
    return [json.loads(line) for line in (root / "mutation-results.jsonl").read_text().splitlines()]


def _target_names(record):
    return [target["name"] for target in record["targets"]]


def test_run_requires_targets_before_analysis(tmp_path):
    result = CliRunner().invoke(main, ["mutations", "run", "-f", str(tmp_path)])
    assert result.exit_code == 1
    assert "Configure mutations.targets" in result.stderr
    assert not (tmp_path / "mutation-results.jsonl").exists()


def test_custom_output_and_command_logs_are_replaced_on_rerun(project):
    args = ["mutations", "run", "-f", str(project), "--target", "unit", "--output", "custom.jsonl"]
    assert CliRunner().invoke(main, args).exit_code == 0
    settings = json.loads((project / "atlas.json").read_text())
    settings["mutations"]["targets"]["unit"]["command"] = [sys.executable, "-c", "print('rerun'); raise SystemExit(1)"]
    (project / "atlas.json").write_text(json.dumps(settings))

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["counts"] == {"killed": 1}
    record = json.loads((project / "custom.jsonl").read_text())
    assert record["outcome"] == "killed"
    assert Path(record["targets"][0]["log"]).read_text() == "rerun\n"
    assert (project / "src/example.py").read_text() == "value = 1 < 2\n"


def test_rules_cannot_be_combined_with_run(project):
    result = CliRunner().invoke(main, ["mutations", "--rules", "run", "-f", str(project)])
    assert result.exit_code == 2
    assert "--rules cannot be combined" in result.stderr
