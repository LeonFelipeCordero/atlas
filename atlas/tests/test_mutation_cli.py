"""Production CLI plan/record/report flows without an embedded test runner."""

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database
from atlas.cli.commands import main
from tests.mutation_support import trial_input


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    shutil.copytree(Path(__file__).parent / "fixtures/mutation_ledger", root)
    database = tmp_path / "atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    monkeypatch.chdir(root)
    migrate_database(database)
    return root


def test_cli_persist_resume_record_and_report(project: Path) -> None:
    runner = CliRunner()
    original = (project / "payments.py").read_bytes()
    plan_result = runner.invoke(main, ["mutation", "plan", "--format", "json"])
    assert plan_result.exit_code == 0, plan_result.output
    plan = json.loads(plan_result.output)
    assert plan["scope"]["mode"] == "folder"
    assert plan["sites"]
    assert len(plan["unexplored_sites"]) == len(plan["sites"])
    assert plan["trials"] == []
    site = plan["sites"][0]
    trial = trial_input(site["original_file_hash"])
    result_path = project / "trial.json"
    result_path.write_text(trial.model_dump_json())
    record_result = runner.invoke(main, ["mutation", "record", "--session", plan["session_id"], "--site", site["site_id"], "--result", str(result_path)])
    assert record_result.exit_code == 0, record_result.output
    acknowledgement = json.loads(record_result.output)
    assert acknowledgement["provenance"] == "agent-reported"
    assert acknowledgement["current_source_status"] == "matches-session"
    report_result = runner.invoke(main, ["mutation", "report", "--session", plan["session_id"], "--format", "json"])
    report = json.loads(report_result.output)
    assert report_result.exit_code == 0
    assert report["trials"][0]["trial_id"] == acknowledgement["trial_id"]
    assert report["outcome_counts"]["survived"] == 1
    markdown = runner.invoke(main, ["mutation", "report", "--session", plan["session_id"]])
    assert markdown.exit_code == 0
    for text in ("agent-reported", "candidate testing gaps", "baseline.log", "mutant.log", "matches-session", "amount >= minimum", "scope"):
        assert text.lower() in markdown.output.lower()
    assert (project / "payments.py").read_bytes() == original
    again = json.loads(runner.invoke(main, ["mutation", "plan"]).output)
    assert again["session_id"] != plan["session_id"]
    assert again["sites"] == plan["sites"]


def test_cli_repeatable_folder_aliases_and_markdown(project: Path) -> None:
    result = CliRunner().invoke(main, ["mutation", "plan", "-f", ".", "--f", "./", "--folder", "../project", "--format", "markdown"])
    assert result.exit_code == 0, result.output
    assert "Mutation experiment ledger" in result.output
    assert "folders: ." in result.output


def test_cli_reports_staleness_without_rewriting_snapshot(project: Path) -> None:
    runner = CliRunner()
    plan = json.loads(runner.invoke(main, ["mutation", "plan"]).output)
    (project / "payments.py").write_text("# modified after planning\n")
    report_result = runner.invoke(main, ["mutation", "report", "--session", plan["session_id"], "--format", "json"])
    assert report_result.exit_code == 0
    report = json.loads(report_result.output)
    assert report["sources"][0]["current_source_status"] == "differs"
    assert report["sites"] == plan["sites"]


@pytest.mark.parametrize("args,message", [
    (["report", "--session", "missing"], "Unknown mutation session"),
    (["plan", "-f", "missing"], "exist"),
    (["plan", "--base", "HEAD"], "Git"),
])
def test_cli_errors_are_actionable(project: Path, args: list[str], message: str) -> None:
    result = CliRunner().invoke(main, ["mutation", *args])
    assert result.exit_code == 1, result.output
    assert message.lower() in result.output.lower()


def test_cli_rejects_malformed_trial(project: Path) -> None:
    result_path = project / "trial.json"
    result_path.write_text('{"schema_version": 9}')
    result = CliRunner().invoke(main, ["mutation", "record", "--session", "missing", "--site", "missing", "--result", str(result_path)])
    assert result.exit_code == 1
    assert "validation" in result.output.lower()
