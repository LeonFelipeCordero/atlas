"""Normalize folder scopes without requiring a Git executable."""

import os
from pathlib import Path

from ..parsing.discovery import (
    _DirectoryContext,
    _directory_rules,
    _include_directory,
    _is_ignored,
    validate_repository,
)


def git_root(path: Path) -> Path | None:
    """Find ordinary repositories and linked worktrees by their metadata marker."""
    return next((parent for parent in (path, *path.parents) if (parent / ".git").exists()), None)


def _inside_other_scope(path: Path, requested: list[Path]) -> bool:
    return any(path != other and path.is_relative_to(other) for other in requested)


def _minimal_scopes(requested: list[Path]) -> tuple[Path, ...]:
    return tuple(path for path in requested if not _inside_other_scope(path, requested))


def normalize_scope(folders: tuple[Path, ...]) -> tuple[Path, tuple[Path, ...]]:
    cwd = Path.cwd().resolve()
    requested = sorted({validate_repository(folder) for folder in folders or (cwd,)})
    scopes = _minimal_scopes(requested)
    repositories = {git_root(path) for path in scopes} - {None}
    if len(repositories) > 1:
        raise ValueError("Mutation folders span disjoint Git repositories")
    common = Path(os.path.commonpath(scopes))
    repository = git_root(common)
    root = repository or (cwd if all(path.is_relative_to(cwd) for path in scopes) else common)
    return validate_repository(root), scopes


def in_scope(path: Path, folders: tuple[Path, ...]) -> bool:
    return any(path.is_relative_to(folder) for folder in folders)


def visible_path(root: Path, relative: str) -> bool:
    """Apply discovery's ancestor rules to a path, including a deleted file."""
    path = root / relative
    rules = []
    atlas_rules = []
    use_gitignore = (root / ".gitignore").is_file()
    base = root
    for name in path.relative_to(root).parts[:-1]:
        rules = _directory_rules(base, rules, ".gitignore") if use_gitignore else []
        atlas_rules = _directory_rules(base, atlas_rules, ".atlasignore")
        context = _DirectoryContext(base, rules, atlas_rules, use_gitignore)
        if not _include_directory(context, name):
            return False
        base /= name
    rules = _directory_rules(base, rules, ".gitignore") if use_gitignore else []
    atlas_rules = _directory_rules(base, atlas_rules, ".atlasignore")
    return not (_is_ignored(path, rules, False) or _is_ignored(path, atlas_rules, False))
