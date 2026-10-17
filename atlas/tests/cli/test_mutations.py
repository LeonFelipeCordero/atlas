"""Mutation CLI contracts with real configuration and isolated analysis/storage."""

import base64
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from atlas.cli import main
from atlas.domain.models import SourceFile
from atlas.domain.repositories import RepositoryDTO, RepositoryError
from atlas.metrics.artifact import GraphArtifact
from atlas.mutations.rules import REGISTRY
from atlas.parsing.mutation_candidates import extract_candidates
from atlas.services.repositories import RepositoryService


@pytest.fixture
def boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    artifact = asdict(GraphArtifact(
        schemaVersion=2, repository={"path": str(tmp_path), "name": "coffee"},
        stats={}, nodes=[], edges=[], views={}, diagnostics=[],
    ))
    with (
        patch("atlas.services.repositories.analyze_folder", return_value=artifact) as analyze,
        patch("atlas.bootstrap.repository_service") as repository,
    ):
        service = MagicMock(spec=RepositoryService)
        service.list.return_value = []
        service.report.return_value = {"mutationCandidates": []}
        repository.return_value.__enter__.return_value = service
        yield analyze, repository, service


def project(name: str, location: str) -> RepositoryDTO:
    return RepositoryDTO(id=name, name=name, location=location, createdAt=1, importedAt=1)


def test_rules_bypasses_config_analysis_and_database(boundaries):
    analyze, repository, _ = boundaries
    Path("atlas.json").write_text("invalid JSON")
    result = CliRunner().invoke(main, ["mutations", "--rules", "--saved", "-f", "/missing"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"rules": [rule.model_dump(mode="json") for rule in REGISTRY]}
    assert result.stderr == ""
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("flag", [None, "-f", "--f", "--folder"])
def test_fresh_defaults_and_folder_aliases(boundaries, flag):
    analyze, repository, _ = boundaries
    root = Path.cwd()
    args = [] if flag is None else [flag, str(root / "sub/..")]
    result = CliRunner().invoke(main, ["mutations", *args])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"schemaVersion": 1, "mutations": []}
    analyze.assert_called_once_with(root)
    repository.assert_not_called()


def test_folder_expands_home(boundaries, monkeypatch: pytest.MonkeyPatch):
    analyze, _, _ = boundaries
    monkeypatch.setenv("HOME", str(Path.cwd()))
    result = CliRunner().invoke(main, ["mutations", "-f", "~/sub/.."])
    assert result.exit_code == 0, result.output
    analyze.assert_called_once_with(Path.cwd())


def test_saved_selects_exact_local_root_without_analysis(boundaries):
    analyze, repository, service = boundaries
    root = Path.cwd()
    service.list.return_value = [
        project("remote", "https://example.com/coffee"),
        project("other", str(root / "other")),
        project("café", str(root / "nested/..")),
    ]
    result = CliRunner().invoke(main, ["mutations", "--saved"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"schemaVersion": 1, "mutations": []}
    analyze.assert_not_called()
    repository.assert_called_once_with()
    service.report.assert_called_once_with("café")
    service.save_folder.assert_not_called()


@pytest.mark.parametrize("count", [0, 2])
def test_saved_requires_one_matching_project(boundaries, count):
    analyze, _, service = boundaries
    service.list.return_value = [project(str(i), str(Path.cwd())) for i in range(count)]
    result = CliRunner().invoke(main, ["mutations", "--saved"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: Expected one indexed project at this folder; run atlas index first\n"
    service.report.assert_not_called()
    analyze.assert_not_called()


@pytest.mark.parametrize(("error_type", "stage"), [
    (RuntimeError, "analysis"), (RuntimeError, "list"), (RuntimeError, "report"),
    (OSError, "analysis"), (ValueError, "analysis"), (RepositoryError, "analysis"),
])
def test_boundary_errors_are_click_errors(boundaries, error_type, stage):
    analyze, _, service = boundaries
    service.list.return_value = [project("coffee", str(Path.cwd()))]
    target = analyze if stage == "analysis" else getattr(service, stage)
    target.side_effect = RepositoryError("unavailable café", 500) if error_type is RepositoryError else error_type("unavailable café")
    result = CliRunner().invoke(main, ["mutations", *([] if stage == "analysis" else ["--saved"])])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: unavailable café\n"
    service.save_folder.assert_not_called()


@pytest.mark.parametrize("config", ["{", '{"mutations":{"rules":["unknown"]}}', '{"mutations":{"rules":{}}}'])
def test_invalid_config_stops_before_boundaries(boundaries, config):
    analyze, repository, _ = boundaries
    Path("atlas.json").write_text(config)
    result = CliRunner().invoke(main, ["mutations"])
    assert result.exit_code == 1
    assert result.stderr.startswith("Error: ")
    analyze.assert_not_called()
    repository.assert_not_called()


@pytest.mark.parametrize("saved", [False, True])
def test_enabled_rule_emits_verified_manifest_without_writes(boundaries, saved):
    analyze, _, service = boundaries
    source = Path(__file__).resolve().parent / "samples/comparison.py"
    original = source.read_bytes()
    target = Path.cwd() / source.name
    target.write_bytes(original)
    Path("atlas.json").write_text(json.dumps({"mutations": {"rules": ["comparison.not-equal-to-equal"]}}))
    candidates = extract_candidates(SourceFile(
        path=target.name, absolute_path=target, language="python", source=original,
    )).candidates
    payload = [candidate.model_dump(mode="json") for candidate in candidates]
    analyze.return_value["mutationCandidates"] = payload
    service.list.return_value = [project("coffee", str(Path.cwd()))]
    service.report.return_value = {"mutationCandidates": payload}

    result = CliRunner().invoke(main, ["mutations", *(["--saved"] if saved else [])])

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["schemaVersion"] == 1
    assert len(report["mutations"]) == 1
    mutation = report["mutations"][0]
    assert mutation["path"] == target.name
    assert mutation["ruleId"] == "comparison.not-equal-to-equal"
    assert mutation["originalText"] == "!="
    assert mutation["replacement"] == "=="
    assert base64.b64decode(mutation["originalBytes"]) == b"!="
    assert base64.b64decode(mutation["replacementBytes"]) == b"=="
    assert target.read_bytes() == original
    service.save_folder.assert_not_called()
    if saved:
        analyze.assert_not_called()
    else:
        analyze.assert_called_once_with(Path.cwd())


def test_saved_malformed_candidates_fail_without_refresh(boundaries):
    analyze, _, service = boundaries
    service.list.return_value = [project("coffee", str(Path.cwd()))]
    service.report.return_value = {"mutationCandidates": [{"id": "invalid"}]}
    result = CliRunner().invoke(main, ["mutations", "--saved"])
    assert result.exit_code == 1
    assert result.stderr.startswith("Error: ")
    analyze.assert_not_called()
    service.save_folder.assert_not_called()
