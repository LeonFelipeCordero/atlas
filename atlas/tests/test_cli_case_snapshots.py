"""Named source states collected independently of operational CLI regressions."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.cli_snapshot_support import case_snapshots as case_snapshots
from tests.source_snapshot_fixture import case_bytes, case_sources

CLI_CASE_IDS = (
    'check-cli-check-defaults-aliases-and-analyzed-root-config',
    'check-cli-check-defaults-aliases-and-analyzed-root-config-mutation-2',
    'check-cli-cycles-fail-check-but-report-stays-quantitative',
    'check-cli-cycles-fail-check-but-report-stays-quantitative-disabled-cycle-limit',
    'check-cli-default-parameter-limit-checks-current-code-and-exit-status',
    'check-cli-default-parameter-limit-checks-current-code-and-exit-status-mutation-2',
    'check-cli-dependency-limits-are-read-from-project-configuration',
    'check-cli-invalid-configuration-invalid-json',
    'check-cli-invalid-configuration-boolean-limit',
    'check-cli-invalid-configuration-unknown-rule',
    'check-cli-partial-config-merges-defaults-and-disabled-checks',
    'check-cli-partial-config-merges-defaults-and-disabled-checks-mutation-2',
    'check-cli-syntax-errors-python-unclosed-return',
    'check-cli-syntax-errors-javascript-unclosed-return',
    'check-cli-report-does-not-apply-project-limits',
    'check-real-dependency-graph-has-trackable-impact-and-instability',
    'dependency-metric-persistence-dependency-metrics-from-normalized-facts',
    'dependency-metric-persistence-normalized-instability-excludes-duplicates-self-and-external-edges',
    'folder-cli-folder-default-and-aliases',
    'folder-cli-report-default-cwd-without-saving',
    'folder-report-cli-default-preserves-existing-graph',
    'folder-report-cli-failed-update-preserves-saved-graph',
    'folder-report-cli-folder-report-creates-and-updates-saved-project',
    'folder-report-cli-source',
    'folder-save-acyclic',
    'folder-save-cycle',
    'normalized-runtime-index-summary-counts-match-source-analysis',
    'persistence-service-reindex-resolves-name-and-rolls-back-failed-write',
    'projects-cli-projects-lists-indexed-and-unindexed-projects',
    'report-cli-index-then-report-analyzes-fresh-folder',
    'size-report-cli-fresh-and-saved-measurements-match-without-sources',
    'size-report-receivers-decorator-comments-and-attributes-at-parameter-threshold',
)

# Mutation-only trees overlay the exact original project, never a generated source.
BASE_CASES = {
    "folder-report-cli-default-preserves-existing-graph": "folder-report-cli-source",
    "folder-report-cli-failed-update-preserves-saved-graph": "folder-report-cli-source",
    "folder-report-cli-folder-report-creates-and-updates-saved-project": "folder-report-cli-source",
    "folder-save-acyclic": "folder-report-cli-source",
    "folder-save-cycle": "folder-report-cli-source",
    "check-cli-cycles-fail-check-but-report-stays-quantitative-disabled-cycle-limit":
        "check-cli-cycles-fail-check-but-report-stays-quantitative",
}


def case_trees(case_id: str) -> tuple[str, ...]:
    base = BASE_CASES.get(case_id, case_id.split("-mutation-")[0])
    return (case_id,) if base == case_id else (base, case_id)


@pytest.fixture
def source_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "source"
    root.mkdir()
    database = tmp_path / "missing/db.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    return root, database


def write_case_tree(root: Path, tree: str) -> None:
    for name in case_sources("cli", tree):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(case_bytes("cli", tree, name))


@pytest.mark.parametrize("case_id", CLI_CASE_IDS)
@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_cli_source_case(case_id: str, output_format: str, source_environment: tuple[Path, Path]) -> None:
    root, database = source_environment
    for tree in case_trees(case_id):
        write_case_tree(root, tree)
    for command in ("report", "check"):
        CliRunner().invoke(main, [command, "-f", str(root), "--format", output_format])
    assert not database.parent.exists()
