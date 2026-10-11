"""Analysis-specific exclusions use Git ignore syntax without requiring Git."""

from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_text
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.parsing.discovery import _repository_paths, discover_files


def write_files(root: Path, names: list[str], case_id: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path = {".git/bad.py": "git-metadata/bad.py"}.get(name, name)
        path.write_text(case_text("operational", case_id, fixture_path))


def source_paths(root: Path) -> set[str]:
    return snapshot_result(
        {source.path for source in discover_files(root)}, "discovered_paths"
    )


@pytest.mark.parametrize("gitignore", [False, True])
def test_atlasignore_patterns_and_negation(tmp_path: Path, gitignore: bool) -> None:
    if gitignore:
        (tmp_path / ".gitignore").touch()
    (tmp_path / ".atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-atlasignore-patterns-and-negation",
            ".atlasignore",
        )
    )
    write_files(
        tmp_path,
        [
            "fixtures/coffee/brew.py",
            "root.py",
            "src/root.py",
            "src/fixtures/keep.py",
            "drop.skip.py",
            "src/drop.skip.py",
            "keep.skip.py",
            "src/keep.skip.py",
            "scratch/bad1.py",
            "scratch/deep/bad2.py",
            "scratch/deep/good.py",
            "#literal.py",
            "!literal.py",
            "main.py",
        ],
        case_id="atlasignore-atlasignore-patterns-and-negation-project",
    )
    assert source_paths(tmp_path) == {
        "src/root.py",
        "src/fixtures/keep.py",
        "keep.skip.py",
        "src/keep.skip.py",
        "scratch/deep/good.py",
        "main.py",
    }


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(
            case_text(
                "operational",
                "atlasignore-atlasignore-preserves-fallback-and-git-metadata-case-01",
                ".atlasignore",
            ),
            id="atlasignore-atlasignore-preserves-fallback-and-git-metadata-case-01",
        ),
        pytest.param(
            case_text(
                "operational",
                "atlasignore-atlasignore-preserves-fallback-and-git-metadata-case-02",
                ".atlasignore",
            ),
            id="atlasignore-atlasignore-preserves-fallback-and-git-metadata-case-02",
        ),
    ],
)
def test_atlasignore_preserves_fallback_and_git_metadata(
    tmp_path: Path, contents: str
) -> None:
    (tmp_path / ".atlasignore").write_text(contents)
    write_files(
        tmp_path,
        ["node_modules/bad.py", "generated/bad.py", ".git/bad.py", "main.py"],
        case_id="atlasignore-atlasignore-preserves-fallback-and-git-metadata-project",
    )
    assert source_paths(tmp_path) == {"main.py"}


def test_atlasignore_cannot_restore_gitignored_paths_or_be_undone_by_gitignore(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text(
        case_text(
            "operational",
            "atlasignore-atlasignore-cannot-restore-gitignored-paths-or-be-undone-by-gitignore",
            ".gitignore",
        )
    )
    (tmp_path / ".atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-atlasignore-cannot-restore-gitignored-paths-or-be-undone-by-gitignore",
            ".atlasignore",
        )
    )
    write_files(
        tmp_path,
        ["git.py", "git-dir/a.py", "gc.py", "gc-dir/a.py", "src/gc.py", "main.py"],
        case_id="atlasignore-atlasignore-cannot-restore-gitignored-paths-or-be-undone-by-gitignore-project",
    )
    (tmp_path / "src/.gitignore").write_text(
        case_text(
            "operational",
            "atlasignore-atlasignore-cannot-restore-gitignored-paths-or-be-undone-by-gitignore",
            "src/.gitignore",
        )
    )
    assert source_paths(tmp_path) == {"main.py"}


@pytest.mark.parametrize("root_atlasignore", [False, True])
def test_nested_atlasignore_is_relative_and_can_override_inherited_patterns(
    tmp_path: Path,
    root_atlasignore: bool,
) -> None:
    if root_atlasignore:
        (tmp_path / ".atlasignore").write_text(
            case_text(
                "operational",
                "atlasignore-nested-atlasignore-is-relative-and-can-override-inherited-patterns",
                ".atlasignore",
            )
        )
    write_files(
        tmp_path,
        [
            "src/keep.skip.py",
            "src/drop.skip.py",
            "src/local.py",
            "src/deep/local.py",
            "other/local.py",
            "other/keep.skip.py",
            "main.py",
        ],
        case_id="atlasignore-nested-atlasignore-is-relative-and-can-override-inherited-patterns-project",
    )
    (tmp_path / "src/.atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-nested-atlasignore-is-relative-and-can-override-inherited-patterns",
            "src/.atlasignore",
        )
    )
    expected = {"src/keep.skip.py", "src/deep/local.py", "other/local.py", "main.py"}
    if not root_atlasignore:
        expected.add("other/keep.skip.py")
    assert source_paths(tmp_path) == expected


def test_negation_requires_visible_parent_directories(tmp_path: Path) -> None:
    (tmp_path / ".atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-negation-requires-visible-parent-directories",
            ".atlasignore",
        )
    )
    write_files(
        tmp_path,
        ["blocked/keep.py", "partial/keep.py", "partial/drop.py"],
        case_id="atlasignore-negation-requires-visible-parent-directories-project",
    )
    (tmp_path / "blocked/.atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-negation-requires-visible-parent-directories",
            "blocked/.atlasignore",
        )
    )
    assert source_paths(tmp_path) == {"partial/keep.py"}


def test_repository_atlasignore_excludes_coffee_only_when_scanning_repository() -> None:
    root = Path(__file__).resolve().parents[2]
    coffee = root / "atlas/tests/fixtures/coffee"
    paths = {path.relative_to(root).as_posix() for path in _repository_paths(root)}
    assert not any(path.startswith("atlas/tests/fixtures/coffee/") for path in paths)
    assert "atlas/tests/test_coffee.py" in paths
    assert "atlas/tests/coffee_fixture.py" in paths
    assert source_paths(coffee / "python")


def test_repository_atlasignore_excludes_data_not_snapshot_test_implementation() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = {path.relative_to(root).as_posix() for path in _repository_paths(root)}
    metadata = {
        "atlas/tests/coffee_features_oo.json",
        "atlas/tests/coffee_consolidation.json",
        "atlas/tests/migration/parsing.json",
        "atlas/tests/snapshots/python-coffee.json",
        "atlas/tests/snapshots/graph-navigation/python-coffee.json",
    }
    assert metadata.isdisjoint(paths)
    assert {"atlas/tests/coffee_pipeline.py", "atlas/tests/coffee_feature_assertions.py",
            "atlas/tests/test_coffee_pipeline.py"} <= paths
    direct = {path.name for path in _repository_paths(root / "atlas/tests/migration")}
    assert "parsing.json" in direct


@pytest.mark.parametrize("command", ["index", "report"])
def test_cli_reanalysis_removes_atlasignored_files_and_findings(
    tmp_path: Path, command: str
) -> None:
    source = tmp_path / "source"
    write_files(
        source,
        ["main.py"],
        case_id="atlasignore-cli-reanalysis-removes-atlasignored-files-and-findings-project",
    )
    fixtures = source / "fixtures"
    fixtures.mkdir()
    (fixtures / "a.py").write_text(
        case_text(
            "operational",
            "atlasignore-cli-reanalysis-removes-atlasignored-files-and-findings",
            "fixtures/a.py",
        )
    )
    (fixtures / "b.py").write_text(
        case_text(
            "operational",
            "atlasignore-cli-reanalysis-removes-atlasignored-files-and-findings",
            "fixtures/b.py",
        )
    )
    database = tmp_path / "graph.sqlite"
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    migrate_database(database)
    with repository_service(database) as service:
        project = service.register({"name": "example", "location": str(source)})
    args = [command, "-f", str(source)]
    if command == "report":
        args.append("--save")
    first = runner.invoke(main, args)
    assert first.exit_code == 0, first.output
    if command == "report":
        assert "## Circular imports" in first.output
    with repository_service(database) as service:
        original = snapshot_result(
            service.get_architecture(project.id), "get_architecture"
        )
        assert original is not None
        assert original.stats.files == 3
        assert snapshot_result(service.report(project.name), "report")[
            "circularImports"
        ]
    (source / ".atlasignore").write_text(
        case_text(
            "operational",
            "atlasignore-cli-reanalysis-removes-atlasignored-files-and-findings",
            ".atlasignore",
        )
    )
    second = runner.invoke(main, args)
    assert second.exit_code == 0, second.output
    if command == "report":
        assert "circularImportGroups: 0" in second.output
    else:
        assert json.loads(second.output)["stats"]["files"] == 1
    with repository_service(database) as service:
        saved = snapshot_result(
            service.get_architecture(project.id), "get_architecture"
        )
        assert saved is not None
        assert saved.stats.files == 1
        assert (
            snapshot_result(service.report(project.name), "report")["circularImports"]
            == []
        )
        facts = snapshot_result(
            service.get_report_facts(project.id), "get_report_facts"
        )
        assert facts is not None
        assert not any(
            (node.path or "").startswith("fixtures/") for node in facts.nodes
        )
    (source / ".atlasignore").unlink()
    restored = runner.invoke(main, args)
    assert restored.exit_code == 0, restored.output
    with repository_service(database) as service:
        saved = snapshot_result(
            service.get_architecture(project.id), "get_architecture"
        )
        assert saved is not None
        assert saved.stats.files == 3
