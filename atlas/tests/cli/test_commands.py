"""Exercise CLI contracts with real reports/config and isolated analysis/storage."""

import json
from copy import deepcopy
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from atlas.cli import main
from atlas.domain.models import GraphNode
from atlas.domain.repositories import GraphDTO, GraphStatsDTO, RepositoryDTO, RepositoryError
from atlas.metrics.artifact import GraphArtifact
from atlas.metrics.config import CheckConfig
from atlas.services.repositories import RepositoryService


@pytest.fixture
def artifact(tmp_path: Path) -> dict[str, Any]:
    nodes: list[GraphNode] = [
        {
            "stableKey": "file:café.py", "type": "file", "kind": "file", "level": "file",
            "language": "python", "name": "café.py", "qualifiedName": "café.py",
            "path": "café.py", "parentStableKey": None, "depth": 0, "ancestorStableKeys": [],
            "properties": {"lineCount": 600},
        },
        {
            "stableKey": "function:brew", "type": "function", "kind": "function", "level": "callable",
            "language": "python", "name": "brew", "qualifiedName": "café.brew",
            "path": "café.py", "parentStableKey": "file:café.py", "startLine": 2,
            "depth": 1, "ancestorStableKeys": ["file:café.py"],
            "properties": {
                "lineCount": 100, "parameterCount": 3, "baseCyclomaticComplexity": 5,
                "cyclomaticComplexity": 8, "nestedCyclomaticComplexity": 3,
                "loopNestedComplexity": 0, "maxDecisionDepth": 3,
            },
        },
    ]
    return asdict(GraphArtifact(
        schemaVersion=2, repository={"path": str(tmp_path), "name": "café"},
        stats={"files": 1, "symbols": 1, "modules": 0, "types": 0, "callables": 1,
               "nodes": 2, "edges": 0, "externalNodes": 0, "parseErrors": 0},
        nodes=nodes, edges=[], views={}, diagnostics=[],
    ))


@pytest.fixture
def boundaries(artifact: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch("atlas.services.repositories.analyze_folder", return_value=artifact) as analyze,
        patch("atlas.bootstrap.repository_service") as repository,
    ):
        service = MagicMock(spec=RepositoryService)
        service.save_folder.return_value = GraphDTO(
            repositoryId="coffee", graphRevision="rev-1", schemaVersion=2,
            indexedAt="2026-01-01T00:00:00Z", rootName="café", rootPath=str(tmp_path),
            importedAt=123, stats=GraphStatsDTO.model_validate(artifact["stats"]),
        )
        repository.return_value.__enter__.return_value = service
        yield analyze, repository, service


@pytest.mark.parametrize("command", ["index", "report", "check"])
@pytest.mark.parametrize("flag", [None, "-f", "--f", "--folder"])
def test_folder_defaults_and_aliases(boundaries, command, flag):
    analyze, repository, service = boundaries
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
        repository.return_value.__exit__.assert_called_once_with(None, None, None)
    else:
        repository.assert_not_called()
        assert result.stdout.startswith("# Metrics" if command == "report" else "All checks passed.")


@pytest.mark.parametrize("command", ["index", "report", "check"])
def test_folder_expands_home(boundaries, monkeypatch: pytest.MonkeyPatch, command):
    analyze, _, _ = boundaries
    tmp_path = Path.cwd()
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, [command, "--folder", "~/source/.."])
    assert result.exit_code == 0, result.output
    analyze.assert_called_once_with(tmp_path)


@pytest.mark.parametrize("command", ["report", "check"])
@pytest.mark.parametrize("options", list(product([None, "markdown", "json"], [False, True])))
def test_formats_and_opt_in_save(boundaries, command, options):
    output_format, save = options
    tmp_path = Path.cwd()
    analyze, repository, service = boundaries
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
        assert service.mock_calls == [call.save_folder(tmp_path, analyze.return_value)]
        repository.return_value.__exit__.assert_called_once_with(None, None, None)
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
def test_projects_serializes_domain_values(boundaries, empty):
    analyze, repository, service = boundaries
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
    assert service.mock_calls == [call.list()]
    repository.return_value.__exit__.assert_called_once_with(None, None, None)


@pytest.mark.parametrize("save", [False, True])
@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_check_findings_have_failure_status_and_can_save(boundaries, save, output_format):
    tmp_path = Path.cwd()
    analyze, repository, service = boundaries
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
        repository.return_value.__exit__.assert_called_once_with(None, None, None)
    else:
        repository.assert_not_called()


@pytest.mark.parametrize("disabled", [False, True])
def test_check_null_disables_rule_and_missing_keys_keep_defaults(boundaries, tmp_path: Path, disabled):
    analyze, repository, _ = boundaries
    analyze.return_value["nodes"][1]["properties"]["parameterCount"] = 4
    (tmp_path / "atlas.json").write_text(
        json.dumps({"maxFileLines": None, **({"maxParameters": None} if disabled else {})}), encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["check", "--format", "json"])
    assert result.exit_code == (0 if disabled else 1), result.output
    findings = json.loads(result.stdout)["findings"]
    assert [finding["rule"] for finding in findings] == ([] if disabled else ["maxParameters"])
    repository.assert_not_called()


def test_check_reads_target_config_not_cwd(boundaries, tmp_path: Path):
    analyze, repository, _ = boundaries
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
def test_check_unavailable_measurement_is_a_finding(boundaries, output_format):
    analyze, _, _ = boundaries
    del analyze.return_value["nodes"][1]["properties"]["parameterCount"]
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
def test_analysis_diagnostics_are_reported(boundaries, command, output_format):
    analyze, repository, _ = boundaries
    diagnostic = {"severity": "error", "language": "python", "path": "café.py", "message": "Parse failed"}
    analyze.return_value["diagnostics"] = [diagnostic]
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
def test_empty_analysis_is_successful(boundaries, command):
    analyze, repository, _ = boundaries
    analyze.return_value = {"nodes": [], "edges": [], "diagnostics": []}
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
def test_check_configured_limits_use_real_metrics(boundaries, tmp_path: Path, case):
    rule, limit, actual = case
    _, repository, _ = boundaries
    (tmp_path / "atlas.json").write_text(json.dumps({rule: limit}), encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--format", "json"])
    assert result.exit_code == 1
    assert result.stderr == ""
    finding, = json.loads(result.stdout)["findings"]
    assert (finding["rule"], finding["actual"], finding["limit"]) == (rule, actual, limit)
    repository.assert_not_called()


@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_check_circular_imports_and_dependency_findings(boundaries, tmp_path: Path, output_format):
    analyze, repository, _ = boundaries
    artifact = analyze.return_value
    other = deepcopy(artifact["nodes"][0])
    other.update(stableKey="file:tea.py", name="tea.py", qualifiedName="tea.py", path="tea.py")
    artifact["nodes"].append(other)
    artifact["edges"] = [
        {"sourceStableKey": f"file:{source}", "targetStableKey": f"file:{target}",
         "type": "IMPORTS", "confidence": "EXTRACTED", "path": source, "line": 1,
         "evidence": "import", "sourceType": "file", "sourceKind": "file", "sourceLevel": "file",
         "targetType": "file", "targetKind": "file", "targetLevel": "file"}
        for source, target in [("café.py", "tea.py"), ("tea.py", "café.py")]
    ]
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


def test_unreadable_config_fails_before_analysis(boundaries, tmp_path: Path):
    analyze, repository, _ = boundaries
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
def test_invalid_config_fails_before_analysis_or_saving(boundaries, tmp_path: Path, source):
    analyze, repository, _ = boundaries
    config = tmp_path / "atlas.json"
    config.write_text(source, encoding="utf-8")
    result = CliRunner().invoke(main, ["check", "--save", "--format", "json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert f"Error: Invalid {config}:" in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("command", ["index", "projects", "report", "check"])
@pytest.mark.parametrize("case", list(product(
    [OSError, ValueError, RuntimeError, RepositoryError], ["operation", "open", "close"],
)))
def test_boundary_errors_are_click_errors(boundaries, command, case):
    error_type, stage = case
    analyze, repository, service = boundaries
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
    else:
        assert repository.return_value.__exit__.call_count == 1


@pytest.mark.parametrize("command", ["index", "report", "check"])
@pytest.mark.parametrize("error_type", [OSError, ValueError, RuntimeError, RepositoryError])
def test_analysis_failure_never_opens_database(boundaries, command, error_type):
    analyze, repository, service = boundaries
    analyze.side_effect = RepositoryError("analysis failed", 400) if error_type is RepositoryError else error_type("analysis failed")
    result = CliRunner().invoke(main, [command, *(["--save"] if command != "index" else [])])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: analysis failed\n"
    repository.assert_not_called()
    service.save_folder.assert_not_called()


@pytest.mark.parametrize("command", ["report", "check"])
@pytest.mark.parametrize("output_format", ["yaml", "JSON", ""])
def test_invalid_format_does_not_analyze_or_open_database(boundaries, command, output_format):
    analyze, repository, _ = boundaries
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
def test_usage_errors_have_no_side_effects(boundaries, args, message):
    analyze, repository, _ = boundaries
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert message in result.stderr
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("command", [None, "index", "projects", "report", "check"])
def test_help_has_no_side_effects(boundaries, command):
    analyze, repository, _ = boundaries
    result = CliRunner().invoke(main, [*([command] if command else []), "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout
    if command in {"index", "report", "check"}:
        assert "[default: .]" in result.stdout
    if command in {"report", "check"}:
        assert "--save" in result.stdout and "[default: markdown]" in result.stdout
    analyze.assert_not_called()
    repository.assert_not_called()


def test_check_help_documents_defaults(boundaries):
    analyze, repository, _ = boundaries
    result = CliRunner().invoke(main, ["check", "--help"])
    assert result.exit_code == 0, result.output
    for rule, value in CheckConfig().model_dump().items():
        if value is not None:
            assert f"{rule}={value}" in result.stdout
    assert "Null disables a check" in result.stdout
    analyze.assert_not_called()
    repository.assert_not_called()
