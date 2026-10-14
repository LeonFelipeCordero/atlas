"""Folder planning preserves discovery rules and exact source snapshots."""

import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from atlas.mutation import plan_mutation


CODE = b"def brew(ready):\n    if ready:\n        return 1\n    return 0\n"


def put(root: Path, path: str, source: bytes = CODE) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    return target


def test_default_folder_without_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    put(tmp_path, "brew.py")
    put(tmp_path, "plain.py", b"answer = 42\n")
    put(tmp_path, "other.go", b"package main\n")
    session = plan_mutation(())
    assert session.root == str(tmp_path)
    assert session.scope.mode == "folder"
    assert session.scope.folders == ["."]
    assert UUID(session.session_id)
    assert datetime.fromisoformat(session.created_at).utcoffset() == timedelta(0)
    assert {source.path for source in session.sources} == {"brew.py", "plain.py", "other.go"}
    assert {site.path for site in session.sites} == {"brew.py"}
    assert any(item.code == "unsupported-language" for item in session.limitations)
    with pytest.raises(ValueError):
        session.root = "changed"


def test_overlaps_and_ignore_ancestry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("src/ignored.py\n")
    (tmp_path / ".atlasignore").write_text("src/private/\n")
    put(tmp_path, "src/visible.py")
    put(tmp_path, "src/ignored.py")
    put(tmp_path, "src/private/secret.py")
    put(tmp_path, "outside.py")
    folders = (Path("src"), tmp_path / "src", Path("src/private"))
    session = plan_mutation(folders)
    assert session.scope.folders == ["src"]
    assert [source.path for source in session.sources] == ["src/visible.py"]


def test_scoped_planning_never_reads_other_sources_or_subtree_ignores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    put(tmp_path, "src/brew.py")
    put(tmp_path, "outside.py")
    put(tmp_path, "outside/other.py")
    (tmp_path / "outside/.atlasignore").write_text("other.py\n")
    read_bytes, read_text = Path.read_bytes, Path.read_text

    def scoped_bytes(path):
        if path == tmp_path / "outside.py" or path.is_relative_to(tmp_path / "outside"):
            raise PermissionError("out-of-scope file")
        return read_bytes(path)

    def scoped_text(path, *args, **kwargs):
        if path.is_relative_to(tmp_path / "outside"):
            raise PermissionError("out-of-scope ignore file")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", scoped_bytes)
    monkeypatch.setattr(Path, "read_text", scoped_text)
    session = plan_mutation((Path("src"),))
    assert [source.path for source in session.sources] == ["src/brew.py"]
    assert session.sites


def test_literal_backslashes_in_posix_source_paths_are_preserved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    put(tmp_path, "odd\\name.py")
    session = plan_mutation(())
    assert session.sources[0].path == "odd\\name.py"
    assert all(site.path == session.sources[0].path for site in session.sites)


def test_outside_folders_use_common_ancestor(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    put(tmp_path, "a/a.py")
    put(tmp_path, "b/b.py")
    session = plan_mutation((tmp_path / "b", tmp_path / "a"))
    assert session.root == str(tmp_path)
    assert session.scope.folders == ["a", "b"]
    assert [source.path for source in session.sources] == ["a/a.py", "b/b.py"]


def test_repository_marker_preserves_root_ignores_without_git(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("src/ignored.py\n")
    put(tmp_path, "src/ignored.py")
    put(tmp_path, "src/brew.py")
    monkeypatch.chdir(tmp_path / "src")
    monkeypatch.setenv("PATH", "")
    session = plan_mutation(())
    assert session.root == str(tmp_path)
    assert session.scope.folders == ["src"]
    assert [source.path for source in session.sources] == ["src/brew.py"]


def test_disjoint_repositories_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a", "b"):
        (tmp_path / name / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="disjoint"):
        plan_mutation((tmp_path / "a", tmp_path / "b"))


def test_snapshot_and_extraction_share_captured_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = CODE.replace(b"ready", "caf\u00e9".encode()).replace(b"\n", b"\r\n")
    put(tmp_path, "brew.py", raw)
    session = plan_mutation(())
    snapshot = session.sources[0]
    assert base64.b64decode(snapshot.content_base64) == raw
    assert snapshot.original_file_hash == hashlib.sha256(raw).hexdigest()
    assert session.sites
    for site in session.sites:
        assert site.original_file_hash == snapshot.original_file_hash
        assert raw[site.span.start_byte:site.span.end_byte].decode() == site.expression
