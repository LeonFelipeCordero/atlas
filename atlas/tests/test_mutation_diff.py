"""Exact base selection over captured working bytes, including deletion ownership."""

import base64
import hashlib
import subprocess
from pathlib import Path

import pytest

from atlas.mutation import plan_mutation
from atlas.mutation import planning


CODE = b"def brew(ready):\n    if ready:\n        return 1\n    return 0\n"
TWO = CODE + b"\ndef other(ready):\n    if ready:\n        return 2\n    return 0\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout.decode().strip()


def put(root: Path, path: str, source: bytes = CODE) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    return target


@pytest.fixture
def repository(tmp_path, monkeypatch):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(root: Path) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", "snapshot")
    return git(root, "rev-parse", "HEAD")


def assert_captured_source(session, path: str, expected: bytes):
    captured = next(source for source in session.sources if source.path == path)
    assert base64.b64decode(captured.content_base64) == expected
    assert captured.original_file_hash == hashlib.sha256(expected).hexdigest()
    assert all(site.original_file_hash == captured.original_file_hash for site in session.sites if site.path == path)


def test_exact_base_staged_unstaged_untracked_and_ignores(repository):
    root = repository
    (root / ".gitignore").write_text("ignored.py\n")
    for name in ("staged.py", "unstaged.py", "unchanged.py", "plain.py"):
        put(root, name, CODE if name != "plain.py" else b"x = 1\n")
    base = commit(root)
    put(root, "staged.py", CODE.replace(b"return 1", b"return 3"))
    git(root, "add", "staged.py")
    # Further unstaged edits to a staged file must supersede the index snapshot.
    latest = CODE.replace(b"return 1", b"return 4")
    put(root, "staged.py", latest)
    put(root, "unstaged.py", CODE.replace(b"return 1", b"return 5"))
    put(root, "plain.py", b"x = 2\n")
    put(root, "new.py")
    put(root, "ignored.py")
    session = plan_mutation((), base)
    assert session.scope.resolved_base == base
    assert session.scope.requested_base == base
    assert session.scope.mode == "git-diff"
    assert {source.path for source in session.sources} == {"staged.py", "unstaged.py", "new.py", "plain.py"}
    assert {site.path for site in session.sites} == {"staged.py", "unstaged.py", "new.py"}
    assert_captured_source(session, "staged.py", latest)


def test_requested_commit_not_merge_base_and_folder_intersection(repository):
    root = repository
    put(root, "src/brew.py")
    put(root, "outside.py")
    initial = commit(root)
    put(root, "src/brew.py", CODE.replace(b"return 1", b"return 3"))
    second = commit(root)
    git(root, "checkout", "--detach", initial)
    put(root, "outside.py", CODE.replace(b"return 1", b"return 9"))
    session = plan_mutation((Path("src"),), second)
    assert session.scope.resolved_base == second
    assert [source.path for source in session.sources] == ["src/brew.py"]
    assert session.sites


def test_module_change_does_not_select_functions(repository):
    root = repository
    put(root, "brew.py", b"if enabled:\n    value = 1\n\n" + TWO)
    base = commit(root)
    put(root, "brew.py", b"if enabled:\n    value = 2\n\n" + TWO)
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable is None and site.diff_relationship == "changed-module" for site in session.sites)


def test_changed_return_selects_unchanged_predicate_only_in_owning_function(repository):
    root = repository
    put(root, "brew.py", TWO)
    base = commit(root)
    put(root, "brew.py", TWO.replace(b"return 1", b"return 3"))
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and "::brew@" in site.callable for site in session.sites)
    assert all(site.diff_relationship == "changed-callable" for site in session.sites)


def test_deletion_only_maps_shifted_surviving_callable_not_neighbor(repository):
    root = repository
    before = b"# old heading\n" + CODE.replace(b"    return 0\n", b"    unused = 1\n    return 0\n") + TWO[len(CODE):]
    put(root, "brew.py", before)
    base = commit(root)
    put(root, "brew.py", TWO)
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and "::brew@" in site.callable for site in session.sites)
    assert not any(item.code in {"deleted-callable", "ambiguous-callable-mapping"} for item in session.limitations)


def test_deleted_callable_not_executable_and_boundary_not_next_callable(repository):
    root = repository
    put(root, "brew.py", TWO)
    base = commit(root)
    put(root, "brew.py", TWO[len(CODE) + 1:])
    session = plan_mutation((), base)
    assert not session.sites
    assert any(item.code == "deleted-callable" for item in session.limitations)


def test_deletion_leaving_surviving_callable_without_sites_is_explicit(repository):
    root = repository
    put(root, "brew.py", CODE)
    base = commit(root)
    put(root, "brew.py", b"def brew(ready):\n    return 0\n")
    session = plan_mutation((), base)
    assert not session.sites
    assert session.sources[0].path == "brew.py"
    assert any(item.code == "no-executable-sites" for item in session.limitations)


def test_deleted_file_and_rename_snapshots(repository):
    root = repository
    old = put(root, "old.py")
    put(root, "deleted.py")
    base = commit(root)
    old.rename(root / "renamed.py")
    (root / "deleted.py").unlink()
    session = plan_mutation((), base)
    assert {source.path: source.deleted for source in session.sources} == {"old.py": True, "deleted.py": True, "renamed.py": False}
    assert {site.path for site in session.sites} == {"renamed.py"}
    assert {item.path for item in session.limitations if item.code == "deleted-file"} == {"old.py", "deleted.py"}
    assert all(base64.b64decode(source.content_base64) == CODE for source in session.sources)


def test_ambiguous_repeated_callable_mapping_diagnosed(repository):
    root = repository
    put(root, "brew.py", CODE + CODE)
    base = commit(root)
    put(root, "brew.py", CODE + CODE.replace(b"    return 0\n", b""))
    session = plan_mutation((), base)
    assert not session.sites
    assert any(item.code == "ambiguous-callable-mapping" for item in session.limitations)


def test_disk_changes_after_discovery_do_not_change_snapshot_or_diff(repository, monkeypatch):
    put(repository, "brew.py", CODE)
    base = commit(repository)
    captured = CODE.replace(b"return 1", b"return 3")
    put(repository, "brew.py", captured)
    discover = planning.discover_files

    def capture_then_rewrite(root, **kwargs):
        files = discover(root, **kwargs)
        put(root, "brew.py", CODE)
        return files

    monkeypatch.setattr(planning, "discover_files", capture_then_rewrite)
    session = plan_mutation((), base)
    assert session.sites
    assert base64.b64decode(session.sources[0].content_base64) == captured
    assert all(site.original_file_hash == hashlib.sha256(captured).hexdigest() for site in session.sites)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b"const f = x => x > 0, g = x => x > 2;\n", b"const f = x => x >= 0, g = x => x > 2;\n"),
        (b"const f = x => x >= 0, g = x => x > 2;\n", b"const f = x => x > 0, g = x => x > 2;\n"),
        (b"const f = x => x > 0, g = x => x > 2;\n", b"const f = x => x > 1, g = x => x > 2;\n"),
        (b"const f = x => { if (x) return 1; return 0; }, g = x => x > 2;\n",
         b"const f = x => { if (x) return 3; return 0; }, g = x => x > 2;\n"),
        (b"const f = x => { if (x) return 1; return 0; }, g = x => x > 2;\n",
         b"const f = x => { if (x) return 1; log(x); return 0; }, g = x => x > 2;\n"),
        (b"const f = x => { if (x) return 1; log(x); return 0; }, g = x => x > 2;\n",
         b"const f = x => { if (x) return 1; return 0; }, g = x => x > 2;\n"),
    ],
)
def test_same_line_arrow_changes_select_only_owning_callable(repository, before, after):
    put(repository, "brew.js", before)
    base = commit(repository)
    put(repository, "brew.js", after)
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and "::f@" in site.callable for site in session.sites)
    assert not session.limitations


@pytest.mark.parametrize("replacement", [b"x >= 0", b"x > 1", b"x > 0 && x < 9"])
def test_arrow_body_change_excludes_assignment_prefix_module_owner(repository, replacement):
    before = b"const f = x => x > 0; if (enabled) run();\n"
    put(repository, "brew.js", before)
    base = commit(repository)
    put(repository, "brew.js", before.replace(b"x > 0", replacement))
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and "::f@" in site.callable for site in session.sites)
    assert not session.limitations


@pytest.mark.parametrize("deleting", [False, True])
def test_same_line_module_boundary_insert_delete_excludes_neighboring_callable(repository, deleting):
    plain = b"const f = x => x > 0; if (enabled) run();\n"
    extra = b"const f = x => x > 0; log(); if (enabled) run();\n"
    put(repository, "brew.js", extra if deleting else plain)
    base = commit(repository)
    put(repository, "brew.js", plain if deleting else extra)
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable is None for site in session.sites)
    assert not session.limitations


def test_same_line_deleted_callable_does_not_select_surviving_neighbor(repository):
    put(repository, "brew.js", b"const f = x => x > 0, g = x => x > 2;\n")
    base = commit(repository)
    put(repository, "brew.js", b"const g = x => x > 2;\n")
    session = plan_mutation((), base)
    assert not session.sites
    assert any(item.code == "deleted-callable" for item in session.limitations)
    assert any(item.code == "no-executable-sites" for item in session.limitations)


@pytest.mark.parametrize("dedent_predicate", [False, True])
def test_indentation_only_changes_select_affected_current_ownership(repository, dedent_predicate):
    before = b"def brew(ready):\n    value = 0\n    if ready:\n        value = 1\n    value = 2\n"
    after = (
        before.replace(b"    if ready:\n        value = 1\n    value = 2", b"if ready:\n    value = 1\nvalue = 2")
        if dedent_predicate else before.replace(b"    value = 2", b"value = 2")
    )
    put(repository, "brew.py", before)
    base = commit(repository)
    put(repository, "brew.py", after)
    session = plan_mutation((), base)
    assert session.sites
    assert all((site.callable is None) == dedent_predicate for site in session.sites)


def test_javascript_newline_only_return_change_selects_callable(repository):
    before = b"function brew(x) { return x > 0; }\n"
    put(repository, "brew.js", before)
    base = commit(repository)
    put(repository, "brew.js", before.replace(b"return ", b"return\n"))
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and "::brew@" in site.callable for site in session.sites)


def test_blank_line_deletion_does_not_select_neighboring_callable(repository):
    before = CODE + b"\n" + TWO[len(CODE):]
    put(repository, "brew.py", before)
    base = commit(repository)
    put(repository, "brew.py", CODE + TWO[len(CODE):])
    session = plan_mutation((), base)
    assert not session.sites


@pytest.mark.parametrize("case", [
    ("js", "js", b"const unused = 1; ", "C.f"),
    ("ts", "ts", b"const unused = 1; ", "C.f"),
    ("tsx", "ts", b"const unused = 1; ", "C.f"),
    ("ts", "ts", b"const unused = 2; ", "A.f"),
    ("tsx", "ts", b"const unused = 2; ", "A.f"),
    ("py", "py", b"threshold > 0", "brew"),
    ("py", "py", b"nested_limit > 0", "other.nested"),
])
def test_class_field_abstract_method_and_decorator_changes_select_only_owner(repository, case):
    suffix, grammar_suffix, change, owner = case
    before = (Path(__file__).parent / "fixtures/mutation" / f"ownership.{grammar_suffix}").read_bytes()
    path = f"ownership.{suffix}"
    put(repository, path, before)
    base = commit(repository)
    replacement = change.replace(b"> 0", b"> 1") if suffix == "py" else b""
    put(repository, path, before.replace(change, replacement))
    session = plan_mutation((), base)
    assert session.sites
    assert all(site.callable and f"::{owner}@" in site.callable for site in session.sites)
    assert all(site.diff_relationship == "changed-callable" for site in session.sites)
    if suffix == "py":
        assert ("comparison", replacement.decode()) in [(site.kind, site.expression) for site in session.sites]
    assert not session.limitations


def test_revision_option_injection_rejected(repository):
    put(repository, "brew.py")
    commit(repository)
    with pytest.raises(ValueError):
        plan_mutation((), "--help")


def test_base_requires_git_but_folder_mode_does_not(repository, monkeypatch):
    put(repository, "brew.py")
    commit(repository)
    monkeypatch.setenv("PATH", "")
    assert plan_mutation(()).sites
    with pytest.raises(ValueError, match="Git is required"):
        plan_mutation((), "HEAD")
