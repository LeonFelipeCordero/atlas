"""Focused discovery tests with mocked I/O and real ignore-rule matching."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pathspec import GitIgnoreSpec

from atlas.parsing import discovery


def test_discover_files_sorts_paths_and_preserves_raw_bytes(monkeypatch, tmp_path):
    # Given unsorted sources and files whose detected languages must be excluded.
    root = tmp_path
    paths = [root / name for name in ("z.py", "src/a.ts", "unknown", "legacy.c")]
    contents = {paths[0]: b"\xff\x00\r\n", paths[1]: b"export {};\n"}
    detector = Mock(side_effect={
        "z.py": "python", "a.ts": "typescript", "unknown": None, "legacy.c": "c",
    }.__getitem__)
    reader = Mock(side_effect=contents.__getitem__)
    monkeypatch.setattr(discovery, "_repository_paths", Mock(return_value=paths))
    monkeypatch.setattr(discovery, "detect_language_from_path", detector)
    monkeypatch.setattr(Path, "read_bytes", lambda path: reader(path))

    # When sources are discovered without a native parser.
    sources = discovery.discover_files(root)

    # Then records have sorted, root-relative POSIX paths and unchanged bytes.
    assert [(source.path, source.absolute_path, source.language, source.source)
            for source in sources] == [
        ("src/a.ts", paths[1], "typescript", b"export {};\n"),
        ("z.py", paths[0], "python", b"\xff\x00\r\n"),
    ]


@pytest.mark.parametrize("language", [None, "not-a-grammar", *sorted(discovery.EXCLUDED_LANGUAGES)])
def test_detect_language_rejects_unknown_and_excluded_languages(monkeypatch, language):
    # Given a detector result that cannot be imported.
    monkeypatch.setattr(discovery, "detect_language_from_path", Mock(return_value=language))

    # When a nested source path is inspected, then no language is accepted.
    assert discovery.detect_language(Path("src/source.ext")) is None
    assert not discovery.is_supported_language(language)


def test_detect_language_uses_only_basename(monkeypatch):
    # Given a detector that recognizes a basename, not a full path.
    detector = Mock(side_effect=lambda name: "python" if name == "main.py" else None)
    monkeypatch.setattr(discovery, "detect_language_from_path", detector)

    # When detection receives a nested path, then it still recognizes the source.
    assert discovery.detect_language(Path("nested/src/main.py")) == "python"


@pytest.mark.parametrize("stage", ["traversal", "detection", "read"])
def test_discover_files_propagates_failures(monkeypatch, tmp_path, stage):
    # Given a failure at one of discovery's I/O boundaries.
    failure = OSError(f"{stage} failed")
    paths = Mock(return_value=[tmp_path / "main.py"])
    detector = Mock(return_value="python")
    reader = Mock(return_value=b"pass\n")
    {"traversal": paths, "detection": detector, "read": reader}[stage].side_effect = failure
    monkeypatch.setattr(discovery, "_repository_paths", paths)
    monkeypatch.setattr(discovery, "detect_language_from_path", detector)
    monkeypatch.setattr(Path, "read_bytes", reader)

    # When discovery runs, then it exposes the original failure, not partial results.
    with pytest.raises(OSError) as caught:
        discovery.discover_files(tmp_path)
    assert caught.value is failure


def test_discover_files_rejects_paths_outside_root(monkeypatch, tmp_path):
    # Given a malformed traversal result outside the repository.
    monkeypatch.setattr(discovery, "_repository_paths", Mock(return_value=[tmp_path.parent / "a.py"]))
    monkeypatch.setattr(discovery, "detect_language_from_path", Mock(return_value="python"))

    # When discovery builds a record, then relative-path validation fails.
    with pytest.raises(ValueError):
        discovery.discover_files(tmp_path)


@pytest.mark.parametrize("is_directory", [True, False])
def test_validate_repository_resolves_and_requires_directory(monkeypatch, tmp_path, is_directory):
    # Given a path with an unresolved parent segment.
    root = tmp_path / "child" / ".."
    monkeypatch.setattr(Path, "is_dir", Mock(return_value=is_directory))

    # When validated, then it returns the canonical path or rejects a non-directory.
    if is_directory:
        assert discovery.validate_repository(root) == tmp_path
    else:
        with pytest.raises(ValueError, match="Repository does not exist"):
            discovery.validate_repository(root)


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_directory_policy_switches_defaults_but_keeps_atlas_and_git_exclusions(tmp_path, use_gitignore):
    # Given Git rules, Atlas rules, and names covered by built-in exclusions.
    context = discovery._DirectoryContext(
        tmp_path,
        [(tmp_path, GitIgnoreSpec.from_lines(["git-only/", "!atlas-only/", "!.git/"]))],
        [(tmp_path, GitIgnoreSpec.from_lines(["atlas-only/", "!node_modules/"]))],
        use_gitignore,
    )
    names = [".git", "node_modules", "generated-code", "git-only", "atlas-only", "src"]

    # When filtering directories, then Git mode replaces defaults, not Atlas rules.
    visible = discovery._visible_directories(context, names)

    assert visible == (["node_modules", "generated-code", "src"] if use_gitignore else ["git-only", "src"])
    assert names == [".git", "node_modules", "generated-code", "git-only", "atlas-only", "src"]


@pytest.mark.parametrize("name", sorted(discovery.IGNORED_DIRECTORIES) + ["generated", "my-generated-code"])
def test_default_directory_policy_excludes_build_and_generated_names(tmp_path, name):
    # Given discovery without a root .gitignore.
    context = discovery._DirectoryContext(tmp_path, [], [], False)

    # When a built-in excluded name is evaluated, then it cannot be traversed.
    assert not discovery._include_directory(context, name)


@pytest.mark.parametrize("case", [
    ("keep.py", False, False),
    ("drop.py", False, True),
    ("other.txt", False, False),
    ("cache", True, True),
    ("cache", False, False),
])
def test_ignore_rules_apply_nested_overrides_and_directory_markers(tmp_path, case):
    name, is_dir, expected = case
    # Given a parent exclusion and child overrides; unmatched child rules must not reset it.
    child = tmp_path / "src"
    rules = [
        (tmp_path, GitIgnoreSpec.from_lines(["*.py", "cache/"])),
        (child, GitIgnoreSpec.from_lines(["!keep.py", "unrelated.txt"])),
    ]

    # When matching a child path, then the last matching rule determines its state.
    assert discovery._is_ignored(child / name, rules, is_dir) is expected


def test_directory_files_require_both_rule_sets_to_allow_a_file(tmp_path):
    # Given conflicting negations, ordered negations, and a Git metadata file.
    context = discovery._DirectoryContext(
        tmp_path,
        [(tmp_path, GitIgnoreSpec.from_lines(["*.py", "!keep.py", "!atlas.py"]))],
        [(tmp_path, GitIgnoreSpec.from_lines(["atlas.py", "!drop.py", "!.git"]))],
        True,
    )

    # When filtering names, then neither rule set can undo the other's exclusion.
    files = discovery._directory_files(context, [".git", "keep.py", "drop.py", "atlas.py", "note.txt"])

    assert files == [tmp_path / "keep.py", tmp_path / "note.txt"]


@pytest.mark.parametrize("exists", [False, True])
def test_directory_rules_copy_inherited_rules_and_load_local_spec(monkeypatch, tmp_path, exists):
    # Given inherited rules and an optional child ignore file.
    inherited = [(tmp_path, GitIgnoreSpec.from_lines(["*.py"]))]
    child = tmp_path / "src"
    monkeypatch.setattr(Path, "is_file", Mock(return_value=exists))
    monkeypatch.setattr(Path, "read_text", Mock(return_value="!keep.py\ncache/\n"))

    # When child rules load, then the parent's rule list remains unchanged.
    rules = discovery._directory_rules(child, inherited, ".gitignore")

    assert rules is not inherited
    assert len(inherited) == 1
    assert len(rules) == (2 if exists else 1)
    assert discovery._is_ignored(child / "keep.py", rules, False) is not exists
    assert discovery._is_ignored(child / "drop.py", rules, False)
    assert discovery._is_ignored(child / "cache", rules, True) is exists


@pytest.mark.parametrize("failure", [PermissionError("denied"), UnicodeError("invalid encoding")])
def test_repository_paths_propagates_ignore_read_failures(monkeypatch, tmp_path, failure):
    # Given an unreadable ignore file encountered during traversal.
    monkeypatch.setattr(Path, "is_file", Mock(return_value=True))
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=failure))
    monkeypatch.setattr(discovery.os, "walk", Mock(return_value=[(str(tmp_path), [], [])]))

    # When paths are collected, then the original read failure escapes.
    with pytest.raises(type(failure)) as caught:
        discovery._repository_paths(tmp_path)
    assert caught.value is failure


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_repository_paths_prunes_walk_and_inherits_nested_rules(monkeypatch, tmp_path, use_gitignore):
    # Given a mocked walk with root and nested ignore files, but no physical sources.
    root = tmp_path
    child = root / "src"
    texts = {
        root / ".gitignore": "*.py\n",
        child / ".gitignore": "!keep.py\n",
        root / ".atlasignore": "private/\nsecret.py\n",
        child / ".atlasignore": "local.py\n",
    }
    monkeypatch.setattr(Path, "is_file", lambda path: path in texts and (
        path != root / ".gitignore" or use_gitignore
    ))
    reader = Mock(side_effect=texts.__getitem__)
    monkeypatch.setattr(Path, "read_text", lambda path: reader(path))
    directories = [".git", "node_modules", "private", "src"]
    walk = [(str(root), directories, [".git", "root.py", "note.txt"]),
            (str(child), [], ["keep.py", "drop.py", "secret.py", "local.py"])]
    monkeypatch.setattr(discovery.os, "walk", Mock(return_value=walk))
    # Containment has a separate test; retain the filtered paths here.
    monkeypatch.setattr(discovery, "_contained_files", lambda paths, root: paths)

    # When paths are collected, then walk state is pruned and child rules inherit.
    paths = discovery._repository_paths(root)

    assert directories == (["node_modules", "src"] if use_gitignore else ["src"])
    assert paths == ([root / "note.txt", child / "keep.py"] if use_gitignore else [
        root / "root.py", root / "note.txt", child / "keep.py", child / "drop.py",
    ])


def test_contained_files_rejects_nonfiles_and_external_symlinks(monkeypatch, tmp_path):
    # Given an ordinary file, an internal symlink, an external symlink, and a directory.
    root = tmp_path
    regular, internal, external, directory = [root / name for name in ("a.py", "in.py", "out.py", "src")]
    targets = {regular: regular, internal: regular, external: root.parent / "outside.py"}
    monkeypatch.setattr(Path, "is_file", lambda path: path in targets)
    resolver = Mock(side_effect=targets.__getitem__)
    monkeypatch.setattr(Path, "resolve", lambda path: resolver(path))

    # When checking containment, then safe paths retain their original spelling.
    assert discovery._contained_files([regular, internal, external, directory], root) == [regular, internal]
