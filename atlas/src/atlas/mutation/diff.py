"""Exact-commit byte comparison and conservative callable-level diff selection."""

import subprocess
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from ..domain.mutation import CallableRegion, MutationDiagnostic, MutationExtraction, MutationSite
from ..parsing.discovery import detect_language
from .scope import in_scope, visible_path


def _git(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, check=True)
    except FileNotFoundError as error:
        raise ValueError("Git is required for mutation --base") from error
    except subprocess.CalledProcessError as error:
        raise ValueError(error.stderr.decode(errors="replace").strip()) from error
    return result.stdout


def resolve_base(root: Path, base: str) -> str:
    """Resolve exactly the requested commit, never a merge base or an option."""
    return _git(root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}").decode().strip()


def base_sources(root: Path, commit: str, folders: tuple[Path, ...]) -> dict[str, tuple[str, bytes]]:
    entries = _git(root, "ls-tree", "-r", "-z", commit).split(b"\0")
    sources = {}
    for entry in filter(None, entries):
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        language = detect_language(Path(path))
        if kind != b"blob" or mode == b"120000" or not language:
            continue
        if in_scope(root / path, folders) and visible_path(root, path):
            sources[path] = (language, _git(root, "cat-file", "blob", object_id.decode()))
    return sources


def _line_offsets(source: bytes) -> tuple[list[bytes], list[int]]:
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return lines, offsets


def _owners(regions: list[CallableRegion], start: int, end: int) -> set[str | None]:
    """Partition a changed byte interval into innermost callable/module ownership."""
    boundaries = {start, end}
    for region in regions:
        if start < region.start_byte < end:
            boundaries.add(region.start_byte)
        if start < region.end_byte < end:
            boundaries.add(region.end_byte)
    points = sorted(boundaries)
    owners: set[str | None] = set()
    for left, right in zip(points, points[1:]):
        # Whitespace outside a callable is module-owned, never a neighboring function.
        enclosing = [region for region in regions if region.start_byte <= left and right <= region.end_byte]
        owner = min(enclosing, key=lambda region: region.end_byte - region.start_byte, default=None)
        owners.add(owner.identity if owner else None)
    return owners


def _changed_owners(
    regions: list[CallableRegion], source: bytes, start: int, end: int, indentation: bool,
) -> set[str | None]:
    # Whitespace can change behavior (Python suites or JS automatic semicolons).
    owners = _owners(regions, start, end)
    if not indentation or source[source.rfind(b"\n", 0, start) + 1:start].strip(b" \t"):
        return owners
    # An indent/dedent can change ownership even when no current code bytes changed.
    # Follow only the same physical line, never the next callable after a deletion.
    tail = source[end:].split(b"\n", 1)[0]
    token = end + len(tail) - len(tail.lstrip(b" \t"))
    if token < end + len(tail):
        owners.update(_owners(regions, token, token + 1))
    return owners


def _byte_opcodes(before: bytes, after: bytes) -> list[tuple[str, int, int, int, int]]:
    """Keep line anchors, refining replacements so unrelated same-line owners stay out."""
    old_lines, old_offsets = _line_offsets(before)
    new_lines, new_offsets = _line_offsets(after)
    opcodes = []
    for tag, a, b, c, d in SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
        left, right = old_offsets[a], new_offsets[c]
        if tag != "replace":
            opcodes.append((tag, left, old_offsets[b], right, new_offsets[d]))
            continue
        matcher = SequenceMatcher(None, before[left:old_offsets[b]], after[right:new_offsets[d]], autojunk=False)
        opcodes.extend((kind, left + i, left + j, right + k, right + stop) for kind, i, j, k, stop in matcher.get_opcodes())
    return opcodes


def _mapped_callable(
    region: CallableRegion, candidates: list[CallableRegion], blocks: list[tuple[int, int, int, int]],
) -> CallableRegion | None:
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    for old_start, old_end, new_start, _ in blocks:
        left, right = max(old_start, region.start_byte), min(old_end, region.end_byte)
        mapped = new_start + left - old_start
        if left < right and candidate.start_byte <= mapped < candidate.end_byte:
            return candidate
    return None


def _identity_key(identity: str) -> str:
    # Extraction identities may include a snapshot byte offset; names alone are
    # only candidates, and must also match an unchanged mapped source location.
    name, separator, offset = identity.rpartition("@")
    return name if separator and offset.isdigit() else identity


def _deleted_owners(
    path: str, owners: set[str | None], old: MutationExtraction, current: MutationExtraction,
    blocks: list[tuple[int, int, int, int]],
) -> tuple[set[str | None], list[MutationDiagnostic]]:
    selected: set[str | None] = {None} if None in owners else set()
    diagnostics = []
    old_by_identity: dict[str, list[CallableRegion]] = defaultdict(list)
    new_by_identity: dict[str, list[CallableRegion]] = defaultdict(list)
    for region in old.callables:
        old_by_identity[_identity_key(region.identity)].append(region)
    for region in current.callables:
        new_by_identity[_identity_key(region.identity)].append(region)
    for identity in sorted({_identity_key(owner) for owner in owners if owner is not None}):
        previous, candidates = old_by_identity[identity], new_by_identity[identity]
        mapped = _mapped_callable(previous[0], candidates, blocks) if len(previous) == 1 else None
        if mapped:
            selected.add(mapped.identity)
            continue
        code = "deleted-callable" if not candidates else "ambiguous-callable-mapping"
        diagnostics.append(MutationDiagnostic(path=path, code=code, message=f"Cannot select deleted code in callable {identity!r}: no reliable surviving mapping"))
    return selected, diagnostics


def select_diff_sites(
    path: str, before: bytes, after: bytes, old: MutationExtraction, current: MutationExtraction,
) -> tuple[list[MutationSite], list[MutationDiagnostic]]:
    """Select surviving sites in changed owning callables, not neighboring functions."""
    opcodes = _byte_opcodes(before, after)
    blocks = [(a, b, c, d) for tag, a, b, c, d in opcodes if tag == "equal"]
    changed: set[str | None] = set()
    removed: set[str | None] = set()
    for tag, a, b, c, d in opcodes:
        if tag == "equal":
            continue
        edited = before[a:b] + after[c:d]
        indentation = bool(edited) and not edited.strip(b" \t")
        changed.update(_changed_owners(current.callables, after, c, d, indentation))
        removed.update(_changed_owners(old.callables, before, a, b, indentation))
    mapped, diagnostics = _deleted_owners(path, removed, old, current, blocks)
    changed.update(mapped)
    sites = [site.model_copy(update={"diff_relationship": "changed-callable" if site.callable else "changed-module"}) for site in current.sites if site.callable in changed]
    if removed and not sites:
        diagnostics.append(MutationDiagnostic(path=path, code="no-executable-sites", message="Changed/deleted regions leave no selected executable mutation sites"))
    return sites, diagnostics
