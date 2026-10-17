"""Exercise CLI contracts with real reports/config and isolated analysis/storage."""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from command_scenarios import make_artifact

from atlas.cli import main
from atlas.domain.models import Diagnostic
from atlas.domain.repositories import GraphDTO, GraphStatsDTO, RepositoryDTO, RepositoryError
from atlas.metrics.config import CheckConfig
from atlas.services.repositories import RepositoryService


@pytest.fixture
def scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch("atlas.services.repositories.analyze_folder") as analyze,
        patch("atlas.bootstrap.repository_service") as repository,
    ):
        def create(**overrides: Any):
            artifact = make_artifact(tmp_path, **overrides)
            analyze.return_value = artifact
            service = MagicMock(spec=RepositoryService)
            service.save_folder.return_value = GraphDTO(
                repositoryId="coffee", graphRevision="rev-1", schemaVersion=2,
                indexedAt="2026-01-01T00:00:00Z", rootName="café", rootPath=str(tmp_path),
                importedAt=123, stats=GraphStatsDTO.model_validate(artifact["stats"]),
            )
            repository.return_value.__enter__.return_value = service
            return analyze, repository, service

        yield create


@pytest.mark.parametrize("command", ["index", "report", "check"])
@pytest.mark.parametrize("flag", [None, "-f", "--f", "--folder"])
def test_folder_defaults_and_aliases(scenario, command, flag):
    analyze, repository, service = scenario()
    root = Path.cwd() if flag is None else Path.cwd() / "source"
    root.mkdir(exist_ok=True)
    args = [command, *([] if flag is None else [flag, "source/../source"])]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    analyze.assert_called_once_with(root)
    if command == "index":
        repository.assert_called_once_with()
        service.save_folder.assert_called_once_with(root, analyze.return_value)
        saved = service.save_folder.return_value
        assert json.loads(result.stdout) == {
            "repositoryId": "coffee", "schemaVersion": 2, "stats": saved.stats.model_dump(),
        }
    else:
        repository.assert_not_called()
        assert result.stdout.startswith("# Metrics" if command == "report" else "All checks passed.")


@pytest.mark.parametrize("command", ["index", "report", "check"])
def test_folder_expands_home(scenario, monkeypatch: pytest.MonkeyPatch, command):
    analyze, _, _ = scenario()
    tmp_path = Path.cwd()
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, [command, "--folder", "~/source/.."])
    assert result.exit_code == 0, result.output
    analyze.assert_called_once_with(tmp_path)


@pytest.mark.parametrize("command", ["report", "check"])
@pytest.mark.parametrize("options", list(product([None, "markdown", "json"], [False, True])))
def test_formats_and_opt_in_save(scenario, command, options):
    output_format, save = options
    tmp_path = Path.cwd()
    analyze, repository, service = scenario()
    before = deepcopy(analyze.return_value)
    args = [command, *(["--save"] if save else [])]
    if output_format is not None:
        args += ["--format", output_format]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    analyze.assert_called_once_with(tmp_path)
    assert analyze.return_value == before
    if save:
        repository.assert_called_once_with()
        service.save_folder.assert_called_once_with(tmp_path, analyze.return_value)
    else:
        repository.assert_not_called()
        service.save_folder.assert_not_called()
    if command == "check":
        assert result.stdout == ('{\n  "findings": []\n}\n' if output_format == "json" else "All checks passed.\n")
    else:
        assert_report_output(result.stdout, output_format)


def assert_report_output(output: str, output_format: str | None):
    if output_format == "json":
        report = json.loads(output)
        assert report["summary"] == {
            "files": 1, "modules": 0, "types": 0, "callables": 1,
            "circularImportGroups": 0, "parseErrors": 0,
        }
        assert set(report) == {"summary", "nodes", "circularImports", "diagnostics", "mutationCandidates"}
        file, function = report["nodes"]
        assert file["metrics"]["functionCount"] == file["metrics"]["measuredFunctionCount"] == 1
        assert file["metrics"]["weightedComplexitySum"] == function["metrics"]["weightedComplexity"] == 8
        assert function["metrics"]["cyclomaticComplexity"] == 5
        assert function["metrics"]["nestedDecisionPenalty"] == 3
        assert report["circularImports"] == report["diagnostics"] == report["mutationCandidates"] == []
        assert "café.brew" in output
    else:
        assert output.startswith("# Metrics\n")
        assert "## Files" in output and "## Callables" in output
        assert "Weighted complexity" in output and "`café.py:2`" in output
        assert "repositoryId" not in output


@pytest.mark.parametrize("empty", [False, True])
def test_projects_serializes_domain_values(scenario, empty):
    analyze, repository, service = scenario()
    projects = [] if empty else [
        RepositoryDTO(id="coffee", name="Café", location="/coffee", createdAt=123, importedAt=None),
        RepositoryDTO(id="tea", name="Tea", location="https://example.com/tea", createdAt=456, importedAt=789),
    ]
    service.list.return_value = projects
    result = CliRunner().invoke(main, ["projects"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == [project.model_dump(mode="json") for project in projects]
    if not empty:
        assert "Café" in result.stdout and '\n    "id"' in result.stdout
    analyze.assert_not_called()
    repository.assert_called_once_with()
    service.list.assert_called_once_with()


@pytest.mark.parametrize("save", [False, True])
@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_check_findings_have_failure_status_and_can_save(scenario, save, output_format):
    tmp_path = Path.cwd()
    analyze, repository, service = scenario()
    (tmp_path / "atlas.json").write_text('{"maxParameters": 2}', encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--format", output_format, *(["--save"] if save else [])])
    assert result.exit_code == 1
    assert result.stderr == ""
    if output_format == "json":
        assert json.loads(result.stdout) == {"findings": [{
            "rule": "maxParameters", "metric": "parameterCount", "subject": "café.brew",
            "files": [{"path": "café.py", "line": 2}], "actual": 3, "limit": 2,
            "details": ["Parameters is 3 (maximum: 2)."],
        }]}
    else:
        assert "## maxParameters: `café.brew`" in result.stdout
        assert "Measured: 3; maximum: 2." in result.stdout
        assert "`café.py:2`" in result.stdout
    analyze.assert_called_once_with(tmp_path)
    if save:
        service.save_folder.assert_called_once_with(tmp_path, analyze.return_value)
    else:
        repository.assert_not_called()


@pytest.mark.parametrize("disabled", [False, True])
def test_check_null_disables_rule_and_missing_keys_keep_defaults(scenario, tmp_path: Path, disabled):
    _, repository, _ = scenario(function_metrics={"parameterCount": 4})
    (tmp_path / "atlas.json").write_text(
        json.dumps({"maxFileLines": None, **({"maxParameters": None} if disabled else {})}), encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["check", "--format", "json"])
    assert result.exit_code == (0 if disabled else 1), result.output
    findings = json.loads(result.stdout)["findings"]
    assert [finding["rule"] for finding in findings] == ([] if disabled else ["maxParameters"])
    repository.assert_not_called()


def test_check_reads_target_config_not_cwd(scenario, tmp_path: Path):
    analyze, repository, _ = scenario()
    (tmp_path / "atlas.json").write_text('{"maxParameters": 0}', encoding="utf-8")
    root = tmp_path / "target"
    root.mkdir()
    (root / "atlas.json").write_text('{"maxParameters": 3}', encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "-f", str(root)])
    assert result.exit_code == 0, result.output
    assert result.stdout == "All checks passed.\n"
    analyze.assert_called_once_with(root)
    repository.assert_not_called()


@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_check_unavailable_measurement_is_a_finding(scenario, output_format):
    scenario(function_metrics={"parameterCount": None})
    result = CliRunner().invoke(main, ["check", "--format", output_format])
    assert result.exit_code == 1
    assert result.stderr == ""
    if output_format == "json":
        finding, = json.loads(result.stdout)["findings"]
        assert finding["rule"] == "maxParameters" and finding["actual"] is None
        assert "unavailable" in finding["details"][0]
    else:
        assert "Measured: N/A; maximum: 3." in result.stdout
        assert "unavailable" in result.stdout


@pytest.mark.parametrize("command", ["report", "check"])
@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_analysis_diagnostics_are_reported(scenario, command, output_format):
    diagnostic: Diagnostic = {"severity": "error", "language": "python", "path": "café.py", "message": "Parse failed"}
    _, repository, _ = scenario(diagnostics=[diagnostic])
    result = CliRunner().invoke(main, [command, "--format", output_format])
    assert result.exit_code == (1 if command == "check" else 0), result.output
    assert result.stderr == ""
    if output_format == "json":
        payload = json.loads(result.stdout)
        if command == "check":
            finding, = payload["findings"]
            assert finding["rule"] == "analysis" and finding["details"] == ["Parse failed"]
            assert finding["files"] == [{"path": "café.py"}]
        else:
            assert payload["summary"]["parseErrors"] == 1
            assert payload["diagnostics"] == [diagnostic]
    else:
        assert "Parse failed" in result.stdout and "`café.py`" in result.stdout
    repository.assert_not_called()


@pytest.mark.parametrize("command", ["report", "check"])
def test_empty_analysis_is_successful(scenario, command):
    _, repository, _ = scenario(empty=True)
    result = CliRunner().invoke(main, [command, "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    if command == "check":
        assert payload == {"findings": []}
    else:
        assert all(value == 0 for value in payload["summary"].values())
        assert payload["nodes"] == payload["circularImports"] == []
    repository.assert_not_called()


@pytest.mark.parametrize("case", [
    ("maxFileLines", 599, 600), ("maxFunctionLines", 99, 100),
    ("maxParameters", 2, 3), ("maxWeightedComplexity", 7, 8),
    ("maxDecisionDepth", 2, 3),
])
def test_check_configured_limits_use_real_metrics(scenario, tmp_path: Path, case):
    rule, limit, actual = case
    _, repository, _ = scenario()
    (tmp_path / "atlas.json").write_text(json.dumps({rule: limit}), encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--format", "json"])
    assert result.exit_code == 1
    assert result.stderr == ""
    finding, = json.loads(result.stdout)["findings"]
    assert (finding["rule"], finding["actual"], finding["limit"]) == (rule, actual, limit)
    repository.assert_not_called()


@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_check_circular_imports_and_dependency_findings(scenario, tmp_path: Path, output_format):
    _, repository, _ = scenario(circular_imports=True)
    (tmp_path / "atlas.json").write_text('{"maxChangeImpact": 0, "maxInstability": 0.4}', encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--format", output_format])
    assert result.exit_code == 1
    assert result.stderr == ""
    if output_format == "json":
        findings = json.loads(result.stdout)["findings"]
        assert [(finding["rule"], finding["actual"]) for finding in findings] == [
            ("maxChangeImpact", 1), ("maxInstability", 0.5),
            ("maxChangeImpact", 1), ("maxInstability", 0.5), ("maxCircularImportGroups", 1),
        ]
        assert findings[-1]["files"] == [{"path": "café.py"}, {"path": "tea.py"}]
    else:
        assert "## maxCircularImportGroups" in result.stdout
        assert "café.py → tea.py → café.py" in result.stdout
        assert "## maxChangeImpact" in result.stdout and "## maxInstability" in result.stdout
    repository.assert_not_called()


def test_unreadable_config_fails_before_analysis(scenario, tmp_path: Path):
    analyze, repository, _ = scenario()
    (tmp_path / "atlas.json").mkdir()
    result = CliRunner().invoke(main, ["check", "--save"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Error:" in result.stderr and "atlas.json" in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("source", [
    "{", "[]", '{"unknown": 1}', '{"maxParameters": -1}',
    '{"maxParameters": "3"}', '{"maxInstability": 2}',
    '{"mutations": {"rules": {"arithmetic.add-to-subtract": "-"}}}',
])
def test_invalid_config_fails_before_analysis_or_saving(scenario, tmp_path: Path, source):
    analyze, repository, _ = scenario()
    config = tmp_path / "atlas.json"
    config.write_text(source, encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--save", "--format", "json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert f"Error: Invalid {config}:" in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("case", [
    (command, stage, OSError)
    for command, stage in product(["index", "projects", "report", "check"], ["operation", "open", "close"])
] + [
    ("index", "operation", error_type) for error_type in [ValueError, RuntimeError, RepositoryError]
])
def test_boundary_errors_are_click_errors(scenario, case):
    command, stage, error_type = case
    analyze, repository, service = scenario()
    error = RepositoryError("boundary failed", 503) if error_type is RepositoryError else error_type("boundary failed")
    if stage == "operation":
        operation = service.list if command == "projects" else service.save_folder
        operation.side_effect = error
    else:
        getattr(repository.return_value, "__enter__" if stage == "open" else "__exit__").side_effect = error
    args = [command, *(["--save"] if command in {"report", "check"} else [])]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: boundary failed\n"
    assert isinstance(result.exception, SystemExit)
    if command == "projects":
        analyze.assert_not_called()
    if stage == "open":
        service.list.assert_not_called()
        service.save_folder.assert_not_called()


@pytest.mark.parametrize("command", ["index", "report", "check"])
def test_analysis_failure_never_opens_database(scenario, command):
    analyze, repository, service = scenario()
    analyze.side_effect = OSError("analysis failed")
    result = CliRunner().invoke(main, [command, *(["--save"] if command != "index" else [])])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: analysis failed\n"
    repository.assert_not_called()
    service.save_folder.assert_not_called()


@pytest.mark.parametrize("command", ["report", "check"])
@pytest.mark.parametrize("output_format", ["yaml", "JSON", ""])
def test_invalid_format_does_not_analyze_or_open_database(scenario, command, output_format):
    analyze, repository, _ = scenario()
    result = CliRunner().invoke(main, [command, "--save", "--format", output_format])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Invalid value for '--format'" in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize(("args", "message"), [
    (["index", "--save"], "No such option '--save'"),
    (["projects", "--folder", "."], "No such option '--folder'"),
    (["report", "--skip-save"], "No such option '--skip-save'"),
    (["check", "--skip-save"], "No such option '--skip-save'"),
    (["index", "--folder"], "requires an argument"),
    (["projects", "extra"], "Got unexpected extra argument"),
])
def test_usage_errors_have_no_side_effects(scenario, args, message):
    analyze, repository, _ = scenario()
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert message in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("command", [None, "index", "projects", "report", "check"])
def test_help_has_no_side_effects(scenario, command):
    analyze, repository, _ = scenario()
    result = CliRunner().invoke(main, [*([command] if command else []), "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout
    if command in {"index", "report", "check"}:
        assert "[default: .]" in result.stdout
    if command in {"report", "check"}:
        assert "--save" in result.stdout and "[default: markdown]" in result.stdout
    analyze.assert_not_called()
    repository.assert_not_called()


def test_check_help_documents_defaults(scenario):
    analyze, repository, _ = scenario()
    result = CliRunner().invoke(main, ["check", "--help"])
    assert result.exit_code == 0, result.output
    for rule, value in CheckConfig().model_dump().items():
        if value is not None:
            assert f"{rule}={value}" in result.stdout
    assert "Null disables a check" in result.stdout
    analyze.assert_not_called()
    repository.assert_not_called()
