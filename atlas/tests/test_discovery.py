"""Discovery's exact path sets under Git and fallback policies."""

import subprocess
from pathlib import Path

import pytest

from atlas.parsing.discovery import _repository_paths
from tests.cli_snapshot_support import case_snapshots as case_snapshots, snapshot_result
from tests.source_snapshot_fixture import case_bytes, case_text


def discovered(root: Path) -> set[str]:
    return snapshot_result({path.relative_to(root).as_posix() for path in _repository_paths(root)}, "discovered_paths")


@pytest.mark.parametrize("git_repository", [pytest.param(False, id="without-git"), pytest.param(True, id="with-git")])
def test_gitignore_replaces_fallback_with_or_without_git(tmp_path: Path, git_repository: bool) -> None:
    root = tmp_path
    if git_repository:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text(case_text("operational", "discovery-assert-gitignore-replaces-fallback", ".gitignore"))
    for name in ("ignored", "node_modules", "generated-code"):
        (root / name).mkdir()
        (root / name / "source.ts").write_text(case_text("operational", "discovery-assert-gitignore-replaces-fallback-source", f"{name}/source.ts"))
    for name in ("drop.tmp", "keep.tmp"):
        (root / name).write_bytes(case_bytes("operational", "discovery-gitignore-empty-files", name))
    if git_repository:
        subprocess.run(["git", "-C", str(root), "add", "-f", "ignored/source.ts"], check=True)
    assert discovered(root) == {".gitignore", "node_modules/source.ts", "generated-code/source.ts", "keep.tmp"}


def test_nested_gitignore_and_negation(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".gitignore").write_text(case_text("operational", "discovery-nested-gitignore-and-negation", ".gitignore"))
    nested = root / "src"
    nested.mkdir()
    (nested / ".gitignore").write_text(case_text("operational", "discovery-nested-gitignore-and-negation-mutation-2", "src/.gitignore"))
    for name in ("keep.ts", "drop.ts", "local.txt", "only-root.txt"):
        (nested / name).write_bytes(case_bytes("operational", "discovery-nested-empty-files", f"src/{name}"))
    (root / "only-root.txt").write_bytes(case_bytes("operational", "discovery-nested-empty-files", "only-root.txt"))
    assert discovered(root) == {".gitignore", "src/.gitignore", "src/keep.ts", "src/only-root.txt"}


def test_empty_gitignore_disables_fallback_but_not_git_metadata(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_bytes(case_bytes("operational", "discovery-empty-gitignore-project", ".gitignore"))
    for name in (".git", "dist"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "file.ts").write_bytes(case_bytes("operational", "discovery-empty-gitignore-project", "dist/file.ts"))
    assert discovered(tmp_path) == {".gitignore", "dist/file.ts"}


def test_fallback_excludes_generated_folders_not_files(tmp_path: Path) -> None:
    for name in ("node_modules", "generated", "auto-generated-code", "pregenerated", "src"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "file.ts").write_bytes(case_bytes("operational", "discovery-fallback-project", f"{name}/file.ts"))
    (tmp_path / "src/generated.ts").write_bytes(case_bytes("operational", "discovery-fallback-project", "src/generated.ts"))
    assert discovered(tmp_path) == {"src/file.ts", "src/generated.ts"}
