"""Discover supported language-pack sources using ignore rules, without Git.

A root .gitignore enables nested Git ignore rules; otherwise built-in directory
exclusions apply. .atlasignore rules always add analysis-specific exclusions.
Git metadata and files resolving outside the root are skipped.
Use validate_repository before discover_files. _repository_paths and _is_ignored
are private helpers.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from pathspec import GitIgnoreSpec
from tree_sitter_language_pack import (
    SupportedLanguage,
    available_languages,
    detect_language_from_path,
)

from ..domain.models import SourceFile

# PHPDoc and RBS are companion grammars for unsupported PHP and Ruby.
EXCLUDED_LANGUAGES = frozenset({"c", "cpp", "csharp", "php", "phpdoc", "ruby", "rbs"})
# Include the pinned catalog's on-demand grammars, not only bundled ones.
SUPPORTED_LANGUAGES = (
    frozenset(get_args(SupportedLanguage)) | frozenset(available_languages())
) - EXCLUDED_LANGUAGES


def is_supported_language(language: str | None) -> bool:
    return language in SUPPORTED_LANGUAGES


def require_supported_language(language: str) -> None:
    if not is_supported_language(language):
        raise ValueError(f"Unsupported Python importer language: {language}")


IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".next",
    ".output",
    ".venv",
    "build",
    "coverage",
    "deps",
    "dist",
    "node_modules",
    "target",
    "vendor",
}


def validate_repository(root: Path) -> Path:
    """Resolve a directory for discovery; no Git repository is required.

    Args:
        root: Repository directory, relative or absolute.
    Returns:
        Resolved absolute directory path.
    Raises:
        ValueError: The resolved path is not a directory.
        OSError: Path resolution fails.
        RuntimeError: Path resolution encounters a symlink loop on Python 3.10–3.12.

    Example:
        root = validate_repository(Path("."))
        files = discover_files(root)
    """
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Repository does not exist: {resolved}")
    return resolved


def _is_ignored(
    path: Path, rules: list[tuple[Path, GitIgnoreSpec]], is_dir: bool
) -> bool:
    ignored = False
    for base, spec in rules:
        relative = path.relative_to(base).as_posix() + ("/" if is_dir else "")
        match = spec.check_file(relative)
        if match.include is not None:
            ignored = match.include
    return ignored


def _directory_rules(base: Path, inherited, filename: str):
    rules = inherited.copy()
    ignore_file = base / filename
    if ignore_file.is_file():
        rules.append((base, GitIgnoreSpec.from_lines(ignore_file.read_text().splitlines())))
    return rules


@dataclass(frozen=True)
class _DirectoryContext:
    base: Path
    rules: list[tuple[Path, GitIgnoreSpec]]
    atlas_rules: list[tuple[Path, GitIgnoreSpec]]
    use_gitignore: bool


def _include_directory(directory: _DirectoryContext, name: str) -> bool:
    path = directory.base / name
    if name == ".git" or _is_ignored(path, directory.atlas_rules, True):
        return False
    if directory.use_gitignore:
        return not _is_ignored(path, directory.rules, True)
    return name not in IGNORED_DIRECTORIES and "generated" not in name


def _directory_files(directory: _DirectoryContext, names: list[str]):
    return [
        directory.base / name
        for name in names
        if name != ".git"
        and not _is_ignored(directory.base / name, directory.rules, False)
        and not _is_ignored(directory.base / name, directory.atlas_rules, False)
    ]


def _child_rules(base: Path, directories: list[str], rules):
    return {base / name: rules for name in directories}


def _visible_directories(directory: _DirectoryContext, directories: list[str]):
    return [name for name in directories if _include_directory(directory, name)]


def _repository_paths(root: Path) -> list[Path]:
    root = root.resolve()
    use_gitignore = (root / ".gitignore").is_file()
    directory_rules: dict[Path, list[tuple[Path, GitIgnoreSpec]]] = {}
    atlas_directory_rules: dict[Path, list[tuple[Path, GitIgnoreSpec]]] = {}
    paths = []
    for directory, directories, names in os.walk(root):
        base = Path(directory)
        rules = (
            _directory_rules(base, directory_rules.get(base, []), ".gitignore")
            if use_gitignore else []
        )
        atlas_rules = _directory_rules(base, atlas_directory_rules.get(base, []), ".atlasignore")
        context = _DirectoryContext(base, rules, atlas_rules, use_gitignore)
        directories[:] = _visible_directories(context, directories)
        directory_rules.update(_child_rules(base, directories, rules))
        atlas_directory_rules.update(_child_rules(base, directories, atlas_rules))
        paths.extend(_directory_files(context, names))
    return _contained_files(paths, root)


def _contained_files(paths: list[Path], root: Path) -> list[Path]:
    return [path for path in paths if path.is_file() and path.resolve().is_relative_to(root)]


def detect_language(path: Path) -> str | None:
    """Detect a grammar from the filename without reading the file.

    Args:
        path: Path whose basename is passed to the language pack.
    Returns:
        Language identifier, or None if the filename is unrecognized or unsupported.

    Language-pack detection errors propagate.

    Example:
        language = detect_language(Path("src/main.py"))  # "python"
    """
    language = detect_language_from_path(path.name)
    return language if is_supported_language(language) else None


def discover_files(root: Path) -> list[SourceFile]:
    """Read recognized files in sorted path order, applying discovery ignore rules.

    Args:
        root: Resolved absolute directory, normally from validate_repository.
    Returns:
        Source records with root-relative POSIX paths and raw file bytes.
    Raises:
        OSError: Reading source bytes or ignore files fails.
        UnicodeError: An ignore file cannot be decoded.
        ValueError: A path is not relative to root, or a source record is invalid.
        RuntimeError: Path resolution encounters a symlink loop on Python 3.10–3.12.

    Example:
        files = discover_files(validate_repository(Path(".")))
    """
    files = []
    for path in sorted(_repository_paths(root)):
        language = detect_language(path)
        if language:
            files.append(
                SourceFile(
                    path.relative_to(root).as_posix(), path, language, path.read_bytes()
                )
            )
    return files
