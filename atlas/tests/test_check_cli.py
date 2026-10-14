"""Check reads current sources and root config, saving only when requested."""

import json
from pathlib import Path
from shutil import copytree

import pytest
from click.testing import CliRunner

from atlas.cli import main
from atlas.metrics.config import CheckConfig
from tests.coffee_fixture import FIXTURE_ROOT

VARIANTS = Path(__file__).parent / "fixtures/variants/cli"


def invoke(root: Path, *extra: str):
    return CliRunner().invoke(main, ["check", "-f", str(root), "--format", "json", *extra])


def configure(root: Path, **limits) -> None:
    (root / "atlas.json").write_text(json.dumps({**dict.fromkeys(CheckConfig.model_fields), **limits}))


def test_check_help_describes_model_defaults_and_check_semantics() -> None:
    result = CliRunner().invoke(main, ["check", "--help"])
    assert result.exit_code == 0, result.output
    help_text = " ".join(result.output.split())
    defaults = ", ".join(f"{rule}={default}" for rule, default in CheckConfig().model_dump().items() if default is not None)
    assert f"Missing keys inherit defaults: {defaults}." in help_text
    assert "=None" not in help_text
    assert "maxChangeImpact and maxInstability are disabled by default and apply to files/modules." in help_text
    assert "Null disables a check. Equality passes; violations exit 1." in help_text
    assert "atlas.json in the analyzed folder, without saving by default." in help_text


def test_default_parameter_limit_checks_current_code_and_exit_status(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    copytree(VARIANTS / "station-over-limit", tmp_path, dirs_exist_ok=True)
    configure(tmp_path, maxParameters=CheckConfig().maxParameters)
    result = invoke(tmp_path)
    assert result.exit_code == 1, result.output
    findings = json.loads(result.output)["findings"]
    subject = "src/coffee/brewing/station.py::BrewingStation.ready"
    finding = next(finding for finding in findings if finding["subject"] == subject)
    assert finding["rule"] == "maxParameters"
    assert finding["actual"] == 4 and finding["limit"] == 3
    copytree(VARIANTS / "station-at-limit", tmp_path, dirs_exist_ok=True)
    result = invoke(tmp_path)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["findings"] == [finding for finding in findings if finding["subject"] != subject]


def test_cycles_fail_check_but_report_stays_quantitative(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    configure(tmp_path, maxCircularImportGroups=CheckConfig().maxCircularImportGroups)
    failed = invoke(tmp_path)
    assert failed.exit_code == 1, failed.output
    finding = json.loads(failed.output)["findings"][0]
    assert finding["rule"] == "maxCircularImportGroups"
    assert finding["actual"] == 1 and finding["limit"] == 0
    assert finding["files"] == [
        {"path": "src/coffee/brewing/recipe.py"}, {"path": "src/coffee/reporting/report.py"},
    ]
    result = CliRunner().invoke(main, ["report", "-f", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    measurements = json.loads(result.output)
    assert measurements["summary"]["circularImportGroups"] == 1
    assert measurements["circularImports"][0]["groupSize"] == 2
    assert "findings" not in measurements
    configure(tmp_path, maxCircularImportGroups=None)
    passed = invoke(tmp_path)
    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output) == {"findings": []}


def test_partial_config_merges_defaults_and_disabled_checks(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    config = {"maxParameters": None, "maxWeightedComplexity": None,
              "maxDecisionDepth": None, "maxCircularImportGroups": None}
    (tmp_path / "atlas.json").write_text(json.dumps(config))
    failed = invoke(tmp_path)
    assert failed.exit_code == 1, failed.output
    assert {finding["rule"] for finding in json.loads(failed.output)["findings"]} == {"maxNestedLoops"}
    (tmp_path / "atlas.json").write_text(json.dumps({**config, "maxNestedLoops": None}))
    passed = invoke(tmp_path)
    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output) == {"findings": []}


def test_dependency_limits_are_read_from_project_configuration(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    config = {**dict.fromkeys(CheckConfig.model_fields), "maxChangeImpact": 1, "maxInstability": 0.5}
    (tmp_path / "atlas.json").write_text(json.dumps(config))
    result = invoke(tmp_path)
    assert result.exit_code == 1, result.output
    findings = json.loads(result.output)["findings"]
    assert {finding["rule"] for finding in findings} == {"maxChangeImpact", "maxInstability"}
    relevant = {(finding["subject"], finding["rule"], finding["actual"], finding["limit"]) for finding in findings}
    assert {
        ("src/coffee/inventory/stock.py", "maxChangeImpact", 2, 1),
        ("src/coffee/orders/models.py", "maxChangeImpact", 6, 1),
        ("src/coffee/orders/service.py", "maxInstability", 1.0, 0.5),
    } <= relevant


@pytest.mark.parametrize("flag", ["-f", "--f", "--folder", None])
def test_check_defaults_aliases_and_analyzed_root_config(tmp_path: Path, monkeypatch, flag) -> None:
    project = copytree(FIXTURE_ROOT / "python", tmp_path / "project")
    configure(project, maxCircularImportGroups=1)
    configure(tmp_path, maxCircularImportGroups=0)
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


@pytest.mark.parametrize("source", ["{", '{"maxParameters": true}', '{"unknownRule": 1}'])
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
    copytree(FIXTURE_ROOT / "python", tmp_path, dirs_exist_ok=True)
    copytree(VARIANTS / "station-over-limit", tmp_path, dirs_exist_ok=True)
    configure(tmp_path, maxParameters=0)
    result = CliRunner().invoke(main, ["report", "-f", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Parameters" in result.output and "maximum" not in result.output
    result = CliRunner().invoke(main, ["check", "-f", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert "maxParameters" in result.output and "src/coffee/brewing/station.py:9" in result.output
    assert "maximum: 0" in result.output


def test_missing_analysis_folder_is_an_error(tmp_path: Path) -> None:
    result = invoke(tmp_path / "missing")
    assert result.exit_code != 0
    assert "Repository does not exist" in result.output


@pytest.mark.parametrize("overlay, filename", [
    ("syntax-python", "src/coffee/brewing/recipe.py"),
    ("syntax-javascript", "brewing/Brewer.js"),
])
def test_real_syntax_errors_fail_check_even_with_all_limits_disabled(tmp_path: Path, overlay: str, filename: str) -> None:
    language = "python" if overlay == "syntax-python" else "javascript"
    copytree(FIXTURE_ROOT / language, tmp_path, dirs_exist_ok=True)
    copytree(VARIANTS / overlay, tmp_path, dirs_exist_ok=True)
    configure(tmp_path)
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
