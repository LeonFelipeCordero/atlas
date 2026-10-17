"""Source contracts through public services, migrated SQLite, and real local files."""

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from atlas.domain.navigation import NavigationError
from atlas.domain.repositories import GraphDTO
from atlas.services.factories import navigation_service, repository_service
from atlas.services.navigation_source import MAX_EXCERPT_BYTES, MAX_FILE_BYTES
from tests.services.test_navigation import BREW, EXTERNAL, FILE, artifact


def save(database: Path, payload: dict[str, Any]) -> GraphDTO:
    with repository_service(database) as repositories:
        return repositories.save_folder(Path(payload["repository"]["path"]), payload)


def write_source(payload: dict[str, Any], data: bytes) -> None:
    (Path(payload["repository"]["path"]) / "café.py").write_bytes(data)
    payload["nodes"][0]["properties"].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize("state", ["no_file", "no_hash", "empty_hash", "ambiguous"])
def test_unverified_metadata_never_releases_text(database: Path, tmp_path: Path, state: str) -> None:
    payload = artifact(tmp_path)
    if state == "no_file":
        payload["nodes"][0].update(level="module", kind="directory")
    elif state == "no_hash":
        payload["nodes"][0]["properties"].pop("sha256")
    elif state == "empty_hash":
        payload["nodes"][0]["properties"]["sha256"] = ""
    else:
        payload["nodes"].append({**payload["nodes"][0], "stableKey": "file:duplicate"})
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=None)
    assert result["source"] == {"status": "unverified", "path": "café.py"}
    assert (tmp_path / "café.py").read_bytes().startswith(b"# menu")


@pytest.mark.parametrize("state", ["no_path", "external_with_path"])
def test_unavailable_nodes_do_not_read_existing_source(database: Path, tmp_path: Path, state: str) -> None:
    payload = artifact(tmp_path)
    if state == "no_path":
        payload["nodes"][1]["path"] = None
        key = BREW
    else:
        payload["nodes"][-1]["path"] = "café.py"
        key = EXTERNAL
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(key, max_lines=10, start_line=None)
    assert result["source"] == {"status": "unavailable"}


@pytest.mark.parametrize("state", ["absolute", "parent", "root", "escape", "loop"])
def test_unsafe_paths_never_release_source(database: Path, tmp_path: Path, state: str) -> None:
    payload = artifact(tmp_path)
    source = tmp_path / "café.py"
    paths = {"absolute": str(source), "parent": "../" + tmp_path.name + "/café.py", "root": "."}
    if state == "escape":
        outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(outside)
    elif state == "loop":
        source.unlink()
        source.symlink_to("café.py")
    path = paths.get(state, "café.py")
    for node in payload["nodes"][:2]:
        node["path"] = path
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=None)
    assert result["source"] == {"status": "unsafe", "path": path}


@pytest.mark.parametrize("state", ["directory", "fifo", "non_directory_parent"])
def test_non_regular_paths_are_unreadable(database: Path, tmp_path: Path, state: str) -> None:
    payload = artifact(tmp_path)
    source = tmp_path / "café.py"
    path = "café.py"
    if state == "directory":
        source.unlink()
        source.mkdir()
    elif state == "fifo":
        source.unlink()
        os.mkfifo(source)
    else:
        path = "café.py/child.py"
    for node in payload["nodes"][:2]:
        node["path"] = path
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=None)
    assert result["source"] == {"status": "unreadable", "path": path}


def test_contained_directory_symlink_keeps_requested_path(database: Path, tmp_path: Path) -> None:
    payload = artifact(tmp_path)
    directory = tmp_path / "actual"
    directory.mkdir()
    (tmp_path / "café.py").rename(directory / "café.py")
    (tmp_path / "alias").symlink_to(directory, target_is_directory=True)
    for node in payload["nodes"][:2]:
        node["path"] = "alias/café.py"
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=1, start_line=None)
    assert result["source"] == {
        "status": "ok", "path": "alias/café.py", "startLine": 2, "endLine": 2,
        "lines": ["def brew():"], "truncated": True, "nextStartLine": 3,
    }


def test_remote_registration_does_not_use_indexing_checkout(database: Path, tmp_path: Path) -> None:
    (tmp_path / "café.py").write_text("def brew():\n    return 1\n")
    with repository_service(database) as repositories:
        repositories.register({"name": "remote", "location": f"https://example.test/{tmp_path.name}"})
        indexed = repositories.index("remote", tmp_path)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        key = navigation.find("café.py", limit=1)["nodes"][0]["stableKey"]
        result = navigation.source(key, max_lines=10, start_line=None)
    assert (tmp_path / "café.py").is_file()
    assert result["source"] == {"status": "missing", "path": "café.py"}


@pytest.mark.parametrize("verified", [True, False])
def test_invalid_utf8_is_decoded_only_after_hash_verification(database: Path, tmp_path: Path, verified: bool) -> None:
    payload = artifact(tmp_path)
    if verified:
        write_source(payload, b"\xff\n")
    indexed = save(database, payload)
    (tmp_path / "café.py").write_bytes(b"\xff\n")
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(FILE, max_lines=10, start_line=None)
    assert result["source"] == {
        "status": "unsupported_encoding" if verified else "changed", "path": "café.py",
    }


@pytest.mark.parametrize("span", [(None, 4), (2, None), (None, None)])
def test_callable_requires_both_span_endpoints(database: Path, tmp_path: Path, span: tuple[int | None, int | None]) -> None:
    payload = artifact(tmp_path)
    payload["nodes"][1].update(startLine=span[0], endLine=span[1])
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=None)
        file = navigation.source(FILE, max_lines=1, start_line=None)
    assert result["source"] == {"status": "span_unavailable", "path": "café.py"}
    assert file["source"]["lines"] == ["# menu"]


@pytest.mark.parametrize("scenario", [
    ((4, 2), None, 4, 2, [], False, None),
    ((0, 0), None, 1, 5, ["# menu", "def brew():", "    grind()", "    return 'coffee'", "# end"], False, None),
    ((2, 4), 1, 2, 4, ["def brew():", "    grind()", "    return 'coffee'"], False, None),
    ((2, 4), 5, 5, 4, [], False, None),
])
def test_span_and_request_boundaries(database: Path, tmp_path: Path, scenario: tuple[Any, ...]) -> None:
    span, requested, start, end, lines, truncated, next_line = scenario
    payload = artifact(tmp_path)
    payload["nodes"][1].update(startLine=span[0], endLine=span[1])
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=requested)
    assert result["source"] == {
        "status": "ok", "path": "café.py", "startLine": start, "endLine": end,
        "lines": lines, "truncated": truncated, "nextStartLine": next_line,
    }


@pytest.mark.parametrize("scenario", [
    (b"", []), (b"\n", [""]), (b"\n\n", ["", ""]),
    (b"first\r\nlast", ["first", "last"]),
    (b"first\r\r\nlast\r", ["first\r", "last"]),
    ("a\rb\v\f\u0085\u2028\u2029\n\n".encode(), ["a\rb\v\f\u0085\u2028\u2029", ""]),
])
def test_file_rows_follow_parser_lf_coordinates(database: Path, tmp_path: Path, scenario: tuple[bytes, list[str]]) -> None:
    data, lines = scenario
    payload = artifact(tmp_path)
    write_source(payload, data)
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(FILE, max_lines=10, start_line=None)
    assert result["source"] == {
        "status": "ok", "path": "café.py", "startLine": 1, "endLine": len(lines),
        "lines": lines, "truncated": False, "nextStartLine": None,
    }


def test_file_ignores_symbol_span_and_clamps_past_eof(database: Path, tmp_path: Path) -> None:
    payload = artifact(tmp_path)
    payload["nodes"][0].update(startLine=2, endLine=4)
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        complete = navigation.source(FILE, max_lines=5, start_line=None)
        past_end = navigation.source(FILE, max_lines=5, start_line=6)
    assert complete["source"] == {
        "status": "ok", "path": "café.py", "startLine": 1, "endLine": 5,
        "lines": ["# menu", "def brew():", "    grind()", "    return 'coffee'", "# end"],
        "truncated": False, "nextStartLine": None,
    }
    assert past_end["source"] == {
        "status": "ok", "path": "café.py", "startLine": 6, "endLine": 5,
        "lines": [], "truncated": False, "nextStartLine": None,
    }


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_file_byte_limit_is_inclusive(database: Path, tmp_path: Path, extra: int) -> None:
    payload = artifact(tmp_path)
    write_source(payload, b"ok\n" + b"x" * (MAX_FILE_BYTES + extra - 3))
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(FILE, max_lines=1, start_line=None)
    expected = {
        "status": "ok", "path": "café.py", "startLine": 1, "endLine": 1,
        "lines": ["ok"], "truncated": True, "nextStartLine": 2,
    } if extra <= 0 else {
        "status": "too_large", "path": "café.py",
        "maxFileBytes": MAX_FILE_BYTES, "maxExcerptBytes": MAX_EXCERPT_BYTES,
    }
    assert result["source"] == expected


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_excerpt_budget_counts_utf8_bytes_but_not_line_endings(database: Path, tmp_path: Path, extra: int) -> None:
    payload = artifact(tmp_path)
    lines = ["é" * (MAX_EXCERPT_BYTES // 2 - 1), "x" * (2 + extra)]
    write_source(payload, ("\r\n".join(lines) + "\r\n").encode())
    indexed = save(database, payload)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(FILE, max_lines=2, start_line=None)
    expected = {
        "status": "ok", "path": "café.py", "startLine": 1, "endLine": 2,
        "lines": lines, "truncated": False, "nextStartLine": None,
    } if extra <= 0 else {
        "status": "too_large", "path": "café.py",
        "maxFileBytes": MAX_FILE_BYTES, "maxExcerptBytes": MAX_EXCERPT_BYTES,
    }
    assert result["source"] == expected


def test_batch_preserves_order_duplicates_metadata_and_diagnostics(database: Path, tmp_path: Path) -> None:
    indexed = save(database, artifact(tmp_path))
    requested = [EXTERNAL, BREW, FILE, BREW]
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.sources(requested, max_lines=1, start_line=3)
        single = navigation.source(BREW, max_lines=1, start_line=3)
        empty = navigation.sources([], max_lines=1, start_line=None)
        with pytest.raises(NavigationError, match="Node not found: missing"):
            navigation.sources([BREW, "missing"], max_lines=1, start_line=None)
    assert result["sources"] == [
        {"stableKey": EXTERNAL, "status": "unavailable"},
        {"stableKey": BREW, **single["source"]},
        {"stableKey": FILE, **single["source"]},
        {"stableKey": BREW, **single["source"]},
    ]
    assert single["source"] == {
        "status": "ok", "path": "café.py", "startLine": 3, "endLine": 3,
        "lines": ["    grind()"], "truncated": True, "nextStartLine": 4,
    }
    assert result["filters"] == {"keys": requested, "maxLines": 1, "startLine": 3}
    assert single["filters"] == {"key": BREW, "maxLines": 1, "startLine": 3}
    assert result["repositoryId"] == indexed.repositoryId
    assert result["graphRevision"] == indexed.graphRevision
    assert result["indexedAt"] == "2026-01-02T03:04:05Z"
    assert result["diagnostics"] == [{
        "severity": "error", "path": "café.py", "language": "python", "message": "local diagnostic",
    }]
    assert result["diagnosticsTruncated"] is False
    assert empty == {
        "repositoryId": indexed.repositoryId, "graphRevision": indexed.graphRevision,
        "indexedAt": "2026-01-02T03:04:05Z", "filters": {"keys": [], "maxLines": 1, "startLine": None},
        "sources": [], "diagnostics": [], "diagnosticsTruncated": False,
    }
