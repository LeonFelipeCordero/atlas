"""Verified, independent byte edits. Never compose edits or write source files."""

import base64
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from tree_sitter_language_pack import get_parser

from atlas.domain.models import SourceFile
from atlas.domain.mutation_candidates import MutationCandidate, MutationSpan
from atlas.parsing.mutation_candidates import extract_candidates

from .rules import REGISTRY, validate_rules


class MutationManifest(BaseModel):
    """Bytes are standard base64; identity hashes the canonical remaining fields."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    candidateId: str
    sourceHash: str
    ruleId: str
    ruleVersion: int
    language: str
    path: str
    span: MutationSpan
    originalText: str
    originalBytes: str
    replacement: str
    replacementBytes: str


# Only these grammar nodes represent binary arithmetic. In particular, never
# infer unary/binary from expression text: comments and parentheses defeat that.
_BINARY_ARITHMETIC = {
    "python": {"binary_operator"},
    "elixir": {"binary_operator"},
    "kotlin": {"additive_expression", "multiplicative_expression"},
}


def _binary_spans(source: SourceFile) -> set[tuple[int, int]]:
    allowed = _BINARY_ARITHMETIC.get(source.language, {"binary_expression"})
    pending = [get_parser(source.language).parse(source.source).root_node]
    spans: set[tuple[int, int]] = set()
    while pending:
        node = pending.pop()
        if node.type in allowed:
            spans.add((node.start_byte, node.end_byte))
        pending.extend(node.named_children)
    return spans


def _read_source(root: Path, candidate: MutationCandidate) -> SourceFile:
    path = Path(candidate.path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != candidate.path:
        raise ValueError(f"Unsafe mutation path: {candidate.path}")
    try:
        absolute = (root / path).resolve(strict=True)
        if not absolute.is_relative_to(root):
            raise ValueError(f"Mutation path escapes root: {candidate.path}")
        data = absolute.read_bytes()
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Cannot read mutation source: {candidate.path}") from error
    return SourceFile(path=candidate.path, absolute_path=absolute, language=candidate.language, source=data)


def _manifest(candidate: MutationCandidate, rule_id: str, version: int, replacement: str) -> MutationManifest:
    payload = dict(
        candidateId=candidate.id, sourceHash=candidate.sourceHash,
        ruleId=rule_id, ruleVersion=version, language=candidate.language,
        path=candidate.path, span=candidate.span.model_dump(),
        originalText=candidate.originalText,
        originalBytes=base64.b64encode(candidate.originalText.encode("utf-8")).decode("ascii"),
        replacement=replacement,
        replacementBytes=base64.b64encode(replacement.encode("utf-8")).decode("ascii"),
    )
    identity = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return MutationManifest.model_validate({"id": hashlib.sha256(identity.encode("utf-8")).hexdigest(), **payload})


def _edits(candidate: MutationCandidate, rules: dict[str, list[str]], binary_spans: set[tuple[int, int]]) -> list[MutationManifest]:
    if candidate.kind == "arithmetic" and (candidate.expressionSpan.startByte, candidate.expressionSpan.endByte) not in binary_spans:
        return []
    return [
        _manifest(candidate, rule.id, rule.version, mapping.replacement)
        for rule in REGISTRY if rule.kind == candidate.kind
        for mapping in rule.mappings
        if mapping.language == candidate.language
        and mapping.original == candidate.operator
        and mapping.replacement in rules.get(rule.id, [])
        and mapping.replacement != candidate.originalText
    ]


def _verify_replacement(source: SourceFile, manifest: MutationManifest, kind: str) -> None:
    """Reject lexical collisions (e.g. JS a+--b -> a---b or a*/re/ -> a//re/)."""
    start, end = manifest.span.startByte, manifest.span.endByte
    replacement = manifest.replacement.encode("utf-8")
    modified = SourceFile(
        path=source.path, absolute_path=source.absolute_path, language=source.language,
        source=source.source[:start] + replacement + source.source[end:],
    )
    sites = extract_candidates(modified).candidates
    if not any(site.kind == kind and site.operator == manifest.replacement
               and site.span.startByte == start and site.span.endByte == start + len(replacement)
               for site in sites):
        raise ValueError(f"Unsafe mutation replacement: {manifest.path}:{start}:{manifest.ruleId}")


def generate_manifests(root: Path, candidates: list[MutationCandidate], rules: dict[str, list[str]]) -> list[MutationManifest]:
    """Validate every candidate, even unselected ones; return sorted unique edits.

    Exact re-extraction verifies phase-1 identity, hash, UTF-8 byte coordinates,
    expression/callable spans and text, and grammar provenance together. Any
    stale or forged input fails the whole call, never a partial result. Each
    manifest applies independently against its sourceHash, including when
    candidate expressions overlap. No mutation is applied here.
    """
    validate_rules(rules)
    root = root.resolve()
    verified: dict[tuple[str, str], tuple[SourceFile, dict[str, MutationCandidate], set[tuple[int, int]]]] = {}
    edits: dict[tuple[str, str, int, int, str], MutationManifest] = {}
    for candidate in sorted(candidates, key=lambda item: (item.path, item.language, item.id)):
        key = (candidate.path, candidate.language)
        if key not in verified:
            source = _read_source(root, candidate)
            extracted = {item.id: item for item in extract_candidates(source).candidates}
            verified[key] = (source, extracted, _binary_spans(source) if extracted else set())
        source, extracted, binary_spans = verified[key]
        if extracted.get(candidate.id) != candidate:
            raise ValueError(f"Stale or invalid mutation candidate: {candidate.path}:{candidate.id}")
        for manifest in _edits(candidate, rules, binary_spans):
            _verify_replacement(source, manifest, candidate.kind)
            edit_key = (manifest.path, manifest.sourceHash, manifest.span.startByte, manifest.span.endByte, manifest.replacement)
            edits.setdefault(edit_key, manifest)
    return sorted(edits.values(), key=lambda item: (item.path, item.span.startByte, item.span.endByte, item.ruleId, item.replacement, item.id))
