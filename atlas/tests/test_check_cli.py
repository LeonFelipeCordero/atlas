"""Check reads current sources and root config, saving only when requested."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots
from tests.source_snapshot_fixture import case_text
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli import main


def invoke(root: Path, *extra: str):
    return CliRunner().invoke(main, ["check", "-f", str(root), "--format", "json", *extra])


def test_default_parameter_limit_checks_current_code_and_exit_status(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(case_text('cli', 'check-cli-default-parameter-limit-checks-current-code-and-exit-status', 'app.py'))
    result = invoke(tmp_path)
    assert result.exit_code == 1, result.output
    findings = json.loads(result.output)["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == "maxParameters"
    assert findings[0]["actual"] == 4 and findings[0]["limit"] == 3
    source.write_text(case_text('cli', 'check-cli-default-parameter-limit-checks-current-code-and-exit-status-mutation-2', 'app.py'))
    result = invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"findings": []}


def test_cycles_fail_check_but_report_stays_quantitative(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(case_text('cli', 'check-cli-cycles-fail-check-but-report-stays-quantitative', 'a.py'))
    (tmp_path / "b.py").write_text(case_text('cli', 'check-cli-cycles-fail-check-but-report-stays-quantitative', 'b.py'))
    failed = invoke(tmp_path)
    assert failed.exit_code == 1, failed.output
    assert json.loads(failed.output)["findings"][0]["rule"] == "maxCircularImportGroups"
    result = CliRunner().invoke(main, ["report", "-f", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    measurements = json.loads(result.output)
    assert measurements["summary"]["circularImportGroups"] == 1
    assert measurements["circularImports"][0]["groupSize"] == 2
    assert "findings" not in measurements
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-cycles-fail-check-but-report-stays-quantitative-disabled-cycle-limit', 'atlas.json'))
    passed = invoke(tmp_path)
    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output) == {"findings": []}


def test_partial_config_merges_defaults_and_disabled_checks(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(case_text('cli', 'check-cli-partial-config-merges-defaults-and-disabled-checks', 'app.py'))
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-partial-config-merges-defaults-and-disabled-checks', 'atlas.json'))
    failed = invoke(tmp_path)
    assert failed.exit_code == 1, failed.output
    assert {finding["rule"] for finding in json.loads(failed.output)["findings"]} == {"maxNestedLoops"}
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-partial-config-merges-defaults-and-disabled-checks-mutation-2', 'atlas.json'))
    passed = invoke(tmp_path)
    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output) == {"findings": []}


def test_dependency_limits_are_read_from_project_configuration(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(case_text('cli', 'check-cli-dependency-limits-are-read-from-project-configuration', 'a.py'))
    (tmp_path / "b.py").write_text(case_text('cli', 'check-cli-dependency-limits-are-read-from-project-configuration', 'b.py'))
    (tmp_path / "c.py").write_text(case_text('cli', 'check-cli-dependency-limits-are-read-from-project-configuration', 'c.py'))
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-dependency-limits-are-read-from-project-configuration', 'atlas.json'))
    result = invoke(tmp_path)
    assert result.exit_code == 1, result.output
    findings = json.loads(result.output)["findings"]
    assert {(finding["rule"], finding["actual"], finding["limit"]) for finding in findings} == {
        ("maxChangeImpact", 2, 1), ("maxInstability", 1.0, 0.5),
    }


@pytest.mark.parametrize("flag", ["-f", "--f", "--folder", None])
def test_check_defaults_aliases_and_analyzed_root_config(tmp_path: Path, monkeypatch, flag) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text(case_text('cli', 'check-cli-check-defaults-aliases-and-analyzed-root-config', 'app.py'))
    (project / "atlas.json").write_text(case_text('cli', 'check-cli-check-defaults-aliases-and-analyzed-root-config', 'atlas.json'))
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-check-defaults-aliases-and-analyzed-root-config-mutation-2', 'atlas.json'))
    monkeypatch.chdir(project if flag is None else tmp_path)
    args = ["check"] if flag is None else ["check", flag, str(project)]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    assert result.output == "All checks passed.\n"


def test_check_default_never_opens_database(tmp_path: Path, monkeypatch) -> None:
    from atlas import bootstrap

    def fail(*_args, **_kwargs):
        raise AssertionError("Check must not access the database")

    monkeypatch.setattr(bootstrap, "repository_service", fail)
    monkeypatch.setattr(bootstrap, "migrate_database", fail)
    database = tmp_path / "missing" / "db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    result = invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert not database.parent.exists()


@pytest.mark.parametrize("source", [pytest.param(case_text('cli', 'check-cli-invalid-configuration-invalid-json', 'atlas.json'), id='check-cli-invalid-configuration-invalid-json'), pytest.param(case_text('cli', 'check-cli-invalid-configuration-boolean-limit', 'atlas.json'), id='check-cli-invalid-configuration-boolean-limit'), pytest.param(case_text('cli', 'check-cli-invalid-configuration-unknown-rule', 'atlas.json'), id='check-cli-invalid-configuration-unknown-rule')])
def test_invalid_configuration_fails_before_analysis(tmp_path: Path, monkeypatch, source: str) -> None:
    from atlas.services import repositories

    def fail(_root):
        raise AssertionError("Invalid configuration should prevent analysis")

    monkeypatch.setattr(repositories, "analyze_folder", fail)
    (tmp_path / "atlas.json").write_text(source)
    result = invoke(tmp_path)
    assert result.exit_code != 0
    assert "Invalid" in result.output and "atlas.json" in result.output


def test_report_does_not_apply_project_limits(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(case_text('cli', 'check-cli-report-does-not-apply-project-limits', 'app.py'))
    (tmp_path / "atlas.json").write_text(case_text('cli', 'check-cli-report-does-not-apply-project-limits', 'atlas.json'))
    result = CliRunner().invoke(main, ["report", "-f", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Parameters" in result.output and "maximum" not in result.output
    result = CliRunner().invoke(main, ["check", "-f", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert "maxParameters" in result.output and "app.py:1" in result.output
    assert "maximum: 0" in result.output


def test_missing_analysis_folder_is_an_error(tmp_path: Path) -> None:
    result = invoke(tmp_path / "missing")
    assert result.exit_code != 0
    assert "Repository does not exist" in result.output


@pytest.mark.parametrize("filename, source", [
    pytest.param('bad.py', case_text('cli', 'check-cli-syntax-errors-python-unclosed-return', 'bad.py'), id='check-cli-syntax-errors-python-unclosed-return'),
    pytest.param('bad.js', case_text('cli', 'check-cli-syntax-errors-javascript-unclosed-return', 'bad.js'), id='check-cli-syntax-errors-javascript-unclosed-return'),
])
def test_real_syntax_errors_fail_check_even_with_all_limits_disabled(tmp_path: Path, filename: str, source: str) -> None:
    from atlas.metrics.config import CheckConfig

    (tmp_path / filename).write_text(source)
    (tmp_path / "atlas.json").write_text(json.dumps(dict.fromkeys(CheckConfig.model_fields)))
    failed = invoke(tmp_path)
    assert failed.exit_code == 1, failed.output
    findings = json.loads(failed.output)["findings"]
    assert findings and all(finding["rule"] == "analysis" for finding in findings)
    assert findings[0]["files"] == [{"path": filename}]
    assert "Syntax error at line" in findings[0]["details"][0]
    measured = CliRunner().invoke(main, ["report", "-f", str(tmp_path), "--format", "json"])
    assert measured.exit_code == 0, measured.output
    assert json.loads(measured.output)["summary"]["parseErrors"] == 1
    assert json.loads(measured.output)["diagnostics"][0]["path"] == filename
