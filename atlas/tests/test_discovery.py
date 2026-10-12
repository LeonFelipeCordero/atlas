"""Discovery's exact path sets under Git and fallback policies."""

import subprocess
from pathlib import Path

import pytest

from atlas.parsing.discovery import _repository_paths
from tests.coffee_fixture import FIXTURE_ROOT


COFFEE_SOURCE = FIXTURE_ROOT / "typescript/brewing/Brewer.ts"


def discovered(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in _repository_paths(root)}


def write_source(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(COFFEE_SOURCE.read_bytes())


@pytest.mark.parametrize(
    "git_repository", [pytest.param(False, id="without-git"), pytest.param(True, id="with-git")]
)
def test_gitignore_replaces_fallback_with_or_without_git(
    tmp_path: Path, git_repository: bool
) -> None:
    if git_repository:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored/\n*.tmp\n!keep.tmp\n")
    for name in ("ignored", "node_modules", "generated-code"):
        write_source(tmp_path / name / "source.ts")
    for name in ("drop.tmp", "keep.tmp"):
        write_source(tmp_path / name)
    if git_repository:
        subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "ignored/source.ts"], check=True)
    assert discovered(tmp_path) == {
        ".gitignore", "node_modules/source.ts", "generated-code/source.ts", "keep.tmp",
    }


def test_nested_gitignore_and_negation(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.ts\n/only-root.txt\n")
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / ".gitignore").write_text("!keep.ts\n/local.txt\n")
    for name in ("keep.ts", "drop.ts", "local.txt", "only-root.txt"):
        write_source(nested / name)
    write_source(tmp_path / "only-root.txt")
    assert discovered(tmp_path) == {
        ".gitignore", "src/.gitignore", "src/keep.ts", "src/only-root.txt",
    }


def test_empty_gitignore_disables_fallback_but_not_git_metadata(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").touch()
    for name in (".git", "dist"):
        write_source(tmp_path / name / "file.ts")
    assert discovered(tmp_path) == {".gitignore", "dist/file.ts"}


def test_fallback_excludes_generated_folders_not_files(tmp_path: Path) -> None:
    for name in ("node_modules", "generated", "auto-generated-code", "pregenerated", "src"):
        write_source(tmp_path / name / "file.ts")
    write_source(tmp_path / "src/generated.ts")
    assert discovered(tmp_path) == {"src/file.ts", "src/generated.ts"}
