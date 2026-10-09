import subprocess
import tempfile
import unittest
from pathlib import Path

from atlas.parsing.discovery import _repository_paths


class DiscoveryTest(unittest.TestCase):
    def test_gitignore_replaces_fallback_with_or_without_git(self) -> None:
        for git_repository in (False, True):
            with (
                self.subTest(git_repository=git_repository),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.assert_gitignore_replaces_fallback(Path(directory), git_repository)

    def assert_gitignore_replaces_fallback(
        self, root: Path, git_repository: bool
    ) -> None:
        if git_repository:
            subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text("ignored/\n*.tmp\n!keep.tmp\n")
        for name in ("ignored", "node_modules", "generated-code"):
            (root / name).mkdir()
            (root / name / "source.ts").write_text("export const value = 1\n")
        (root / "drop.tmp").touch()
        (root / "keep.tmp").touch()
        if git_repository:
            subprocess.run(
                ["git", "-C", str(root), "add", "-f", "ignored/source.ts"],
                check=True,
            )
        self.assertEqual(
            {path.relative_to(root).as_posix() for path in _repository_paths(root)},
            {
                ".gitignore",
                "node_modules/source.ts",
                "generated-code/source.ts",
                "keep.tmp",
            },
        )

    def test_nested_gitignore_and_negation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("*.ts\n/only-root.txt\n")
            nested = root / "src"
            nested.mkdir()
            (nested / ".gitignore").write_text("!keep.ts\n/local.txt\n")
            for name in ("keep.ts", "drop.ts", "local.txt", "only-root.txt"):
                (nested / name).touch()
            (root / "only-root.txt").touch()
            self.assertEqual(
                {path.relative_to(root).as_posix() for path in _repository_paths(root)},
                {".gitignore", "src/.gitignore", "src/keep.ts", "src/only-root.txt"},
            )

    def test_empty_gitignore_disables_fallback_but_not_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").touch()
            for name in (".git", "dist"):
                (root / name).mkdir()
                (root / name / "file.ts").touch()
            self.assertEqual(
                {path.relative_to(root).as_posix() for path in _repository_paths(root)},
                {".gitignore", "dist/file.ts"},
            )

    def test_fallback_excludes_generated_folders_not_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "node_modules",
                "generated",
                "auto-generated-code",
                "pregenerated",
                "src",
            ):
                (root / name).mkdir()
                (root / name / "file.ts").touch()
            (root / "src" / "generated.ts").touch()
            self.assertEqual(
                {path.relative_to(root).as_posix() for path in _repository_paths(root)},
                {"src/file.ts", "src/generated.ts"},
            )


if __name__ == "__main__":
    unittest.main()
