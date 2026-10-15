"""Derived exact edits through the production CLI and fresh/saved report API."""

import json
from pathlib import Path
from shutil import copytree

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.mutations.config import MutationConfig
from atlas.mutations.report import build_mutation_report
from atlas.mutations.rules import REGISTRY
from tests.coffee_fixture import FIXTURE_ROOT, SNAPSHOT_ROOT

RULES = [rule.id for rule in REGISTRY]
LANGUAGES = tuple(dict.fromkeys(mapping.language for rule in REGISTRY for mapping in rule.mappings))


@pytest.mark.parametrize("sample", ("", "operators"))
@pytest.mark.parametrize("language", LANGUAGES)
def test_manifest_pipeline_snapshot(language: str, sample: str, tmp_path: Path) -> None:
    root = tmp_path / language
    fixture = FIXTURE_ROOT / "mutations" / language if sample else FIXTURE_ROOT / language
    copytree(fixture, root)
    config = MutationConfig(rules=RULES)
    (root / "atlas.json").write_text(json.dumps({"mutations": config.model_dump()}))
    database = tmp_path / "atlas.sqlite"
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    fresh = runner.invoke(main, ["mutations", "-f", str(root)])
    assert fresh.exit_code == 0, fresh.output
    assert not database.exists()
    result = json.loads(fresh.output)
    snapshot = f"{language}-{sample}.json" if sample else f"{language}.json"
    expected = json.loads((SNAPSHOT_ROOT / "mutations" / snapshot).read_text())
    assert result == expected
    if sample:
        expected_mappings = sorted(
            (rule.id, mapping.original, mapping.replacement)
            for rule in REGISTRY for mapping in rule.mappings if mapping.language == language
        )
        assert sorted((item["ruleId"], item["originalText"], item["replacement"])
                      for item in result["mutations"]) == expected_mappings
        for item in result["mutations"]:
            lines = (root / item["path"]).read_text().splitlines()
            assert "unary" not in lines[item["span"]["startLine"] - 1]
    assert runner.invoke(main, ["mutations", "-f", str(root)]).output == fresh.output
    migrate_database(database)
    indexed = runner.invoke(main, ["index", "-f", str(root)])
    assert indexed.exit_code == 0, indexed.output
    stored = runner.invoke(main, ["mutations", "-f", str(root), "--saved"])
    assert stored.exit_code == 0, stored.output
    assert stored.output == fresh.output
    with repository_service(database) as service:
        project, = service.list()
        report = service.report(project.name)
    assert build_mutation_report(root, report, config) == result
    original_candidates = report["mutationCandidates"]
    (root / "atlas.json").write_text('{"mutations":{"rules":[]}}')
    disabled = runner.invoke(main, ["mutations", "-f", str(root), "--saved"])
    assert disabled.exit_code == 0, disabled.output
    assert json.loads(disabled.output)["mutations"] == []
    with repository_service(database) as service:
        assert service.report(project.name)["mutationCandidates"] == original_candidates
    assert build_mutation_report(root, report, MutationConfig()) == {"schemaVersion": 1, "mutations": []}
    assert all(item["ruleId"].split(".")[0] != "condition" for item in result["mutations"])


def test_saved_sources_are_verified_even_when_disabled(tmp_path: Path) -> None:
    root = tmp_path / "python"
    copytree(FIXTURE_ROOT / "python", root)
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    assert runner.invoke(main, ["index", "-f", str(root)]).exit_code == 0
    source = root / "src/coffee/brewing/brewer.py"
    source.write_bytes(b"# changed\n" + source.read_bytes())
    stale = runner.invoke(main, ["mutations", "-f", str(root), "--saved"])
    assert stale.exit_code == 1
    assert "Stale or invalid mutation candidate" in stale.output
    assert runner.invoke(main, ["mutations", "-f", str(root)]).exit_code == 0
    source.unlink()
    missing = runner.invoke(main, ["mutations", "-f", str(root), "--saved"])
    assert missing.exit_code == 1
    assert "Cannot read mutation source" in missing.output


def test_help_describes_rule_id_list() -> None:
    result = CliRunner().invoke(main, ["mutations", "--help"])
    assert result.exit_code == 0
    assert "mutations.rules is a list of rule IDs" in " ".join(result.output.split())


def test_rule_catalog_does_not_open_database_or_analyze(tmp_path: Path) -> None:
    runner = CliRunner(env={"DATABASE_PATH": str(tmp_path / "absent.sqlite")})
    result = runner.invoke(main, ["mutations", "-f", str(tmp_path / "absent"), "--rules"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"rules": [rule.model_dump(mode="json") for rule in REGISTRY]}
    assert not (tmp_path / "absent.sqlite").exists()
