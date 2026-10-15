"""Identify and inspect candidate sites through analysis, CLI and saved reports."""

import json
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.services.repositories import analyze_folder
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES as COFFEE_LANGUAGES, SNAPSHOT_ROOT

LANGUAGES = COFFEE_LANGUAGES


def source_root(language: str) -> Path:
    return FIXTURE_ROOT / "generic_receivers" / "php" if language == "php" else FIXTURE_ROOT / language


def expected_snapshot(language: str) -> dict:
    root = SNAPSHOT_ROOT / "coffee" / language
    graph = json.loads((root / "graph.json").read_text())
    cli = json.loads((root / "cli.json").read_text())
    return {"candidates": graph["mutationCandidates"],
            "markdown": cli["report-markdown"]["output"].partition("## Mutation candidates")[2]}


def candidate_snapshot(language: str) -> dict:
    result = CliRunner().invoke(main, [
        "report", "-f", str(source_root(language)), "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    markdown = CliRunner().invoke(main, ["report", "-f", str(source_root(language))])
    assert markdown.exit_code == 0, markdown.output
    return {"candidates": report["mutationCandidates"],
            "markdown": markdown.output.partition("## Mutation candidates")[2]}


@pytest.mark.parametrize("language", LANGUAGES)
def test_candidate_pipeline_snapshot(language: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "not-created" / "atlas.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    expected = expected_snapshot(language)
    assert candidate_snapshot(language) == expected
    assert not database.parent.exists()
    artifact = analyze_folder(source_root(language))
    assert artifact["mutationCandidates"] == expected["candidates"]
    assert artifact["stats"]["parseErrors"] == 0
    assert_candidate_bytes(language, expected["candidates"])


def assert_candidate_bytes(language: str, candidates: list[dict]) -> None:
    for candidate in candidates:
        source = (source_root(language) / candidate["path"]).read_bytes()
        assert candidate["sourceHash"] == sha256(source).hexdigest()
        assert_span_bytes(source, candidate["span"], candidate["originalText"])
        assert_span_bytes(source, candidate["expressionSpan"], candidate["expressionText"])
    identities = [candidate["id"] for candidate in candidates]
    assert len(identities) == len(set(identities))


def assert_span_bytes(source: bytes, span: dict, text: str) -> None:
    assert source[span["startByte"]:span["endByte"]].decode() == text
    assert span["startLine"] == source.count(b"\n", 0, span["startByte"]) + 1
    assert span["startColumn"] == span["startByte"] - source.rfind(b"\n", 0, span["startByte"])


@pytest.mark.parametrize("language", (*LANGUAGES, "php"))
def test_saved_candidate_report_matches_fresh_report(language: str, tmp_path: Path) -> None:
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    args = ["report", "-f", str(source_root(language)), "--format", "json"]
    fresh = runner.invoke(main, args)
    saved = runner.invoke(main, [*args, "--save"])
    assert saved.exit_code == 0, saved.output
    assert saved.output == fresh.output
    report = json.loads(fresh.output)
    with repository_service(database) as service:
        project, = service.list()
        stored = service.report(project.name)
        assert stored["mutationCandidates"] == report["mutationCandidates"]
        assert stored["summary"]["parseErrors"] == 0
    again = runner.invoke(main, [*args, "--save"])
    assert again.output == fresh.output


def test_changed_and_deleted_sources_refresh_analysis(tmp_path: Path) -> None:
    root = tmp_path / "coffee"
    root.mkdir()
    copyfile(source_root("python") / "src/coffee/brewing/brewer.py", root / "brewer.py")
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    with repository_service(database) as service:
        saved = service.save_folder(root, analyze_folder(root))
        original = service.get_report_facts(saved.repositoryId)
        assert original is not None and original.mutationCandidates
        source = root / "brewer.py"
        source.write_bytes(source.read_bytes().replace(b"beans > 0", b"beans >= 0"))
        service.save_folder(root, analyze_folder(root))
        changed = service.get_report_facts(saved.repositoryId)
        assert changed is not None and changed.mutationCandidates
        assert {item["id"] for item in changed.mutationCandidates}.isdisjoint(item["id"] for item in original.mutationCandidates)
        assert all(item["sourceHash"] == sha256(source.read_bytes()).hexdigest() for item in changed.mutationCandidates)
        source.unlink()
        service.save_folder(root, analyze_folder(root))
        deleted = service.get_report_facts(saved.repositoryId)
        assert deleted is not None and deleted.mutationCandidates == []
