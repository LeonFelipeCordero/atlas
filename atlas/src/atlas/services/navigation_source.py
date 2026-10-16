"""Verified local source excerpts; source bodies are never persisted."""

import hashlib
import os
import stat
from contextlib import ExitStack
from pathlib import Path

from atlas.domain.navigation import NavigationReader, Record, SourceOptions

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_EXCERPT_BYTES = 16 * 1024


def source_excerpt(reader: NavigationReader, node: Record, options: SourceOptions) -> Record:
    """Return a bounded excerpt only after matching the indexed file's SHA-256.

    Return a status without source for external/pathless nodes, ambiguous or
    unhashed files, changed content, or local read/encoding/span limits.
    """
    path = node["path"]
    if not path or node["level"] == "external":
        return {"status": "unavailable"}
    files = reader.file(path)
    if len(files) != 1 or not files[0]["sha256"]:
        return {"status": "unverified", "path": path}
    status, data = local_bytes(reader.snapshot.root, path)
    if status != "ok":
        return source_status(status, path)
    if hashlib.sha256(data).hexdigest() != files[0]["sha256"]:
        return {"status": "changed", "path": path}
    return verified_excerpt(node, data, options)


def verified_excerpt(node: Record, data: bytes, options: SourceOptions) -> Record:
    """Format already hash-verified bytes as a bounded UTF-8 source excerpt.

    Return a status for invalid encoding, missing symbol spans, or excerpts
    over MAX_EXCERPT_BYTES; this function does not verify the hash itself.
    """
    path = node["path"]
    try:
        lines = source_lines(data)
    except UnicodeDecodeError:
        return {"status": "unsupported_encoding", "path": path}
    if node["level"] != "file" and (node["startLine"] is None or node["endLine"] is None):
        return {"status": "span_unavailable", "path": path}
    excerpt = excerpt_lines(node, lines, options)
    if sum(len(line.encode("utf-8")) for line in excerpt["lines"]) > MAX_EXCERPT_BYTES:
        return source_status("too_large", path)
    return excerpt


def source_lines(data: bytes) -> list[str]:
    """Return UTF-8 lines matching parser coordinates; invalid UTF-8 raises.

    Only LF advances a row; strip CRLF endings and omit a trailing empty row.
    """
    lines = data.decode("utf-8").split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line.removesuffix("\r") for line in lines]


def source_status(status: str, path: str) -> Record:
    """Return a source status/path record, including byte caps for too_large."""
    result: Record = {"status": status, "path": path}
    if status == "too_large":
        result.update(maxFileBytes=MAX_FILE_BYTES, maxExcerptBytes=MAX_EXCERPT_BYTES)
    return result


def local_bytes(root_path: str, relative_path: str) -> tuple[str, bytes]:
    """Read a bounded regular file contained by the canonical repository root.

    Reject absolute paths, parent components, and escapes. Return status/bytes;
    unsafe, missing, unreadable, and oversized files return empty bytes.
    """
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return "unsafe", b""
    try:
        root = Path(root_path).resolve()
        target = (root / relative).resolve()
        if target == root or not target.is_relative_to(root):
            return "unsafe", b""
        return contained_bytes(root, target)
    except RuntimeError:
        return "unsafe", b""
    except FileNotFoundError:
        return "missing", b""
    except OSError:
        return "unreadable", b""


def contained_bytes(root: Path, target: Path) -> tuple[str, bytes]:
    """Read target after the caller verifies canonical containment within root.

    Pin directory descriptors and reject symlink swaps. Return status/bytes
    for regular files within MAX_FILE_BYTES, or empty bytes for size/type
    failures. Propagate OS/path errors for local_bytes to classify.
    """
    with ExitStack() as stack:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, descriptor)
        parts = target.relative_to(root).parts
        for part in parts[:-1]:
            descriptor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            stack.callback(os.close, descriptor)
        file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        stream = stack.enter_context(os.fdopen(file_descriptor, "rb"))
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            return "unreadable", b""
        if info.st_size > MAX_FILE_BYTES:
            return "too_large", b""
        data = stream.read(MAX_FILE_BYTES + 1)
        return ("too_large", b"") if len(data) > MAX_FILE_BYTES else ("ok", data)


def excerpt_lines(node: Record, lines: list[str], options: SourceOptions) -> Record:
    """Return a one-based, span-bounded line page and continuation metadata.

    File nodes use the full file span. Clamp the requested start to the span's
    first line and limit output to max_lines; do not enforce byte limits here.
    """
    first = node["startLine"] or 1
    last = node["endLine"] or len(lines)
    if node["level"] == "file":
        first, last = 1, len(lines)
    start = max(first, options.start_line or first)
    stop = min(last, len(lines), start + options.max_lines - 1)
    excerpt = lines[start - 1:stop] if start <= stop else []
    return {"status": "ok", "path": node["path"], "startLine": start, "endLine": stop,
            "lines": excerpt, "truncated": stop < last, "nextStartLine": stop + 1 if stop < last else None}
