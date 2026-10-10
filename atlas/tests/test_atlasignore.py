"""Analysis-specific exclusions use Git ignore syntax without requiring Git."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.parsing.discovery import _repository_paths, discover_files


def write_files(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n")


def source_paths(root: Path) -> set[str]:
    return {source.path for source in discover_files(root)}


@pytest.mark.parametrize("gitignore", [False, True])
def test_atlasignore_patterns_and_negation(tmp_path: Path, gitignore: bool) -> None:
    if gitignore:
        (tmp_path / ".gitignore").touch()
    (tmp_path / ".atlasignore").write_text(
        "# Analysis exclusions\n\n/fixtures/\n/root.py\n*.skip.py\n"
        "scratch/**/bad?.py\n!keep.skip.py\n\\#literal.py\n\\!literal.py\n"
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
    )
    assert source_paths(tmp_path) == {
        "src/root.py",
        "src/fixtures/keep.py",
        "keep.skip.py",
        "src/keep.skip.py",
        "scratch/deep/good.py",
        "main.py",
    }


@pytest.mark.parametrize("contents", ["", "!node_modules/\n!generated/\n!.git/\n"])
def test_atlasignore_preserves_fallback_and_git_metadata(
    tmp_path: Path, contents: str
) -> None:
    (tmp_path / ".atlasignore").write_text(contents)
    write_files(
        tmp_path, ["node_modules/bad.py", "generated/bad.py", ".git/bad.py", "main.py"]
    )
    assert source_paths(tmp_path) == {"main.py"}


def test_atlasignore_cannot_restore_gitignored_paths_or_be_undone_by_gitignore(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text("git.py\ngit-dir/\n!gc.py\n!gc-dir/\n")
    (tmp_path / ".atlasignore").write_text("!git.py\n!git-dir/\ngc.py\ngc-dir/\n")
    write_files(
        tmp_path,
        ["git.py", "git-dir/a.py", "gc.py", "gc-dir/a.py", "src/gc.py", "main.py"],
    )
    (tmp_path / "src/.gitignore").write_text("!gc.py\n")
    assert source_paths(tmp_path) == {"main.py"}


@pytest.mark.parametrize("root_atlasignore", [False, True])
def test_nested_atlasignore_is_relative_and_can_override_inherited_patterns(
    tmp_path: Path,
    root_atlasignore: bool,
) -> None:
    if root_atlasignore:
        (tmp_path / ".atlasignore").write_text("*.skip.py\n")
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
    )
    (tmp_path / "src/.atlasignore").write_text("*.skip.py\n!keep.skip.py\n/local.py\n")
    expected = {"src/keep.skip.py", "src/deep/local.py", "other/local.py", "main.py"}
    if not root_atlasignore:
        expected.add("other/keep.skip.py")
    assert source_paths(tmp_path) == expected


def test_negation_requires_visible_parent_directories(tmp_path: Path) -> None:
    (tmp_path / ".atlasignore").write_text(
        "blocked/\n!blocked/keep.py\npartial/*\n!partial/keep.py\n"
    )
    write_files(tmp_path, ["blocked/keep.py", "partial/keep.py", "partial/drop.py"])
    (tmp_path / "blocked/.atlasignore").write_text("!keep.py\n")
    assert source_paths(tmp_path) == {"partial/keep.py"}


def test_repository_atlasignore_excludes_coffee_only_when_scanning_repository() -> None:
    root = Path(__file__).resolve().parents[2]
    coffee = root / "atlas/tests/fixtures/coffee"
    paths = {path.relative_to(root).as_posix() for path in _repository_paths(root)}
    assert not any(
        path.startswith("atlas/tests/fixtures/coffee/") for path in paths
    )
    assert "atlas/tests/test_coffee.py" in paths
    assert "atlas/tests/coffee_fixture.py" in paths
    assert source_paths(coffee / "python")


@pytest.mark.parametrize("command", ["index", "report"])
def test_cli_reanalysis_removes_atlasignored_files_and_findings(
    tmp_path: Path, command: str
) -> None:
    source = tmp_path / "source"
    write_files(source, ["main.py"])
    fixtures = source / "fixtures"
    fixtures.mkdir()
    (fixtures / "a.py").write_text("from . import b\n")
    (fixtures / "b.py").write_text("from . import a\n")
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
        original = service.get_architecture(project.id)
        assert original is not None
        assert original.stats.files == 3
        assert service.report(project.name)["circularImports"]
    (source / ".atlasignore").write_text("/fixtures/\n")
    second = runner.invoke(main, args)
    assert second.exit_code == 0, second.output
    if command == "report":
        assert "circularImportGroups: 0" in second.output
    else:
        assert json.loads(second.output)["stats"]["files"] == 1
    with repository_service(database) as service:
        saved = service.get_architecture(project.id)
        assert saved is not None
        assert saved.stats.files == 1
        assert service.report(project.name)["circularImports"] == []
        facts = service.get_report_facts(project.id)
        assert facts is not None
        assert not any((node.path or "").startswith("fixtures/") for node in facts.nodes)
    (source / ".atlasignore").unlink()
    restored = runner.invoke(main, args)
    assert restored.exit_code == 0, restored.output
    with repository_service(database) as service:
        saved = service.get_architecture(project.id)
        assert saved is not None
        assert saved.stats.files == 3
