"""Build self-contained mutation sessions from captured source bytes."""

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..domain.models import SourceFile
from ..domain.mutation import (
    MutationDiagnostic,
    MutationExtraction,
    MutationScope,
    MutationSession,
    MutationSource,
)
from ..parsing.discovery import discover_files
from ..parsing.mutation import extract_mutation_sites
from .diff import base_sources, resolve_base, select_diff_sites
from .scope import normalize_scope


def _snapshot(path: str, language: str, content: bytes) -> MutationSource:
    return MutationSource(
        path=path,
        language=language,
        original_file_hash=hashlib.sha256(content).hexdigest(),
        content_base64=base64.b64encode(content).decode("ascii"),
    )


def _folder_plan(files: list[SourceFile]):
    sources, sites, diagnostics = [], [], []
    for file in files:
        extraction = extract_mutation_sites(file.path, file.language, file.source)
        sources.append(_snapshot(file.path, file.language, file.source))
        sites.extend(extraction.sites)
        diagnostics.extend(extraction.diagnostics)
    return sources, sites, diagnostics


def _diff_plan(files: list[SourceFile], previous: dict[str, tuple[str, bytes]]):
    working = {file.path: file for file in files}
    sources, sites, diagnostics = [], [], []
    for path in sorted(working.keys() | previous.keys()):
        file = working.get(path)
        language, before = previous.get(path, (file.language if file else "", b""))
        if file is None:
            sources.append(_snapshot(path, language, before).model_copy(update={"deleted": True}))
            extraction = extract_mutation_sites(path, language, before)
            diagnostics.extend(extraction.diagnostics)
            diagnostics.append(MutationDiagnostic(path=path, code="deleted-file", message="Deleted source has no executable mutation sites"))
            continue
        if path in previous and file.source == before:
            continue
        sources.append(_snapshot(path, file.language, file.source))
        current = extract_mutation_sites(path, file.language, file.source)
        old = extract_mutation_sites(path, language, before) if path in previous else MutationExtraction()
        selected, limitations = select_diff_sites(path, (before, file.source), (old, current))
        sites.extend(selected)
        diagnostics.extend(current.diagnostics)
        diagnostics.extend(old.diagnostics)
        diagnostics.extend(limitations)
    return sources, sites, diagnostics


def plan_mutation(folders: tuple[Path, ...], base: str | None = None) -> MutationSession:
    """Capture a folder scope or exact-commit working-tree diff without graph state."""
    root, normalized = normalize_scope(folders)
    # Inherit root ignore rules, but filter before reading sources outside scope.
    files = discover_files(root, folders=normalized)
    resolved = resolve_base(root, base) if base is not None else None
    sources, sites, diagnostics = (
        _diff_plan(files, base_sources(root, resolved, normalized))
        if resolved is not None else _folder_plan(files)
    )
    return MutationSession(
        session_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        root=str(root),
        scope=MutationScope(
            mode="git-diff" if base is not None else "folder",
            folders=[path.relative_to(root).as_posix() for path in normalized],
            requested_base=base,
            resolved_base=resolved,
        ),
        sources=sources,
        sites=sites,
        limitations=diagnostics,
    )
