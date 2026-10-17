"""Verification guards with real domain records and mocked external boundaries."""

import base64
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from atlas.domain.models import SourceFile
from atlas.domain.mutation_candidates import (
    MutationCallable,
    MutationCandidate,
    MutationCandidateAnalysis,
    MutationSpan,
)
from atlas.mutations import manifests as module


ROOT = Path("/repo")


def span(start: int, end: int) -> MutationSpan:
    return MutationSpan(
        startByte=start, endByte=end, startLine=1, endLine=1,
        startColumn=start + 1, endColumn=end + 1,
    )


@pytest.fixture
def records():
    def make(data="é + b\r\n".encode(), original="+", language="python", path="src/café.py"):
        start = data.index(original.encode())
        source = SourceFile(path=path, absolute_path=ROOT / path, language=language, source=data)
        candidate = MutationCandidate(
            id="candidate-1", path=path, language=language,
            sourceHash=hashlib.sha256(data).hexdigest(), kind="arithmetic", operator=original,
            span=span(start, start + len(original.encode())), expressionSpan=span(0, len(data)),
            originalText=original, expressionText=data.decode(),
            callable=MutationCallable(name="brew", span=span(0, len(data)), originalText=data.decode()),
        )
        return source, candidate

    return make


def manifest_for(candidate: MutationCandidate, replacement="-") -> module.MutationManifest:
    return module.MutationManifest(
        id="manifest-1", candidateId=candidate.id, sourceHash=candidate.sourceHash,
        ruleId="arithmetic.add-to-subtract", ruleVersion=1,
        language=candidate.language, path=candidate.path, span=candidate.span,
        originalText=candidate.originalText,
        originalBytes=base64.b64encode(candidate.originalText.encode()).decode(),
        replacement=replacement, replacementBytes=base64.b64encode(replacement.encode()).decode(),
    )


@pytest.mark.parametrize("path", [
    "/etc/passwd", "../outside.py", "src/../../outside.py", "src/../inside.py",
    "./inside.py", "src//inside.py", "src/./inside.py", "src/inside.py/", "",
])
def test_read_source_rejects_unsafe_spelling_before_filesystem(records, monkeypatch, path):
    _, candidate = records(path=path)
    resolve = Mock()
    read = Mock()
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "read_bytes", read)

    with pytest.raises(ValueError, match="^Unsafe mutation path:"):
        module._read_source(ROOT, candidate)

    resolve.assert_not_called()
    read.assert_not_called()


@pytest.mark.parametrize("resolved", [Path("/outside/café.py"), Path("/repo-other/café.py")])
def test_read_source_rejects_resolved_escape_before_read(records, monkeypatch, resolved):
    _, candidate = records()
    monkeypatch.setattr(Path, "resolve", Mock(return_value=resolved))
    read = Mock()
    monkeypatch.setattr(Path, "read_bytes", read)

    with pytest.raises(ValueError, match="^Mutation path escapes root: src/café.py$"):
        module._read_source(ROOT, candidate)

    read.assert_not_called()


@pytest.mark.parametrize("operation", ["resolve", "read_bytes"])
@pytest.mark.parametrize("error_type", [FileNotFoundError, PermissionError, IsADirectoryError, OSError, RuntimeError])
def test_read_source_wraps_filesystem_errors_with_cause(records, monkeypatch, operation, error_type):
    _, candidate = records()
    error = error_type("filesystem failure")
    resolve = Mock(return_value=ROOT / candidate.path)
    read = Mock(return_value=b"ignored")
    (resolve if operation == "resolve" else read).side_effect = error
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "read_bytes", read)

    with pytest.raises(ValueError, match="^Cannot read mutation source: src/café.py$") as caught:
        module._read_source(ROOT, candidate)

    assert caught.value.__cause__ is error
    if operation == "resolve":
        read.assert_not_called()


@pytest.mark.parametrize("data", [b"", b"\xff\x00\r\n", "é + b\r\n".encode()])
def test_read_source_preserves_requested_metadata_and_raw_bytes(records, monkeypatch, data):
    _, candidate = records(path="alias/café.py", language="javascript")
    absolute = ROOT / "actual/café.py"
    resolutions = []
    reads = []

    def resolve(path, *, strict=False):
        resolutions.append((path, strict))
        return absolute

    def read(path):
        reads.append(path)
        return data

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "read_bytes", read)

    result = module._read_source(ROOT, candidate)

    assert result == SourceFile(
        path="alias/café.py", absolute_path=absolute, language="javascript", source=data,
    )
    assert resolutions == [(ROOT / "alias/café.py", True)]
    assert reads == [absolute]


@pytest.mark.parametrize(("language", "allowed"), [
    ("python", {"binary_operator"}), ("elixir", {"binary_operator"}),
    ("kotlin", {"additive_expression", "multiplicative_expression"}),
    ("javascript", {"binary_expression"}), ("typescript", {"binary_expression"}),
    ("tsx", {"binary_expression"}), ("java", {"binary_expression"}),
    ("rust", {"binary_expression"}), ("go", {"binary_expression"}),
])
def test_binary_spans_uses_language_grammar_nodes_not_operator_text(records, monkeypatch, language, allowed):
    source, _ = records(language=language)
    kinds = [
        "binary_operator", "binary_expression", "additive_expression",
        "multiplicative_expression", "unary_operator", "unary_expression",
        "assignment_expression", "comment", "identifier",
    ]
    children = [SimpleNamespace(type=kind, start_byte=i, end_byte=i + 2,
                                text=b"a + b", named_children=[])
                for i, kind in enumerate(kinds)]
    nested = SimpleNamespace(type=next(iter(allowed)), start_byte=20, end_byte=40, named_children=children)
    root = SimpleNamespace(type="module", start_byte=0, end_byte=100, named_children=[nested, nested])
    parser = Mock()
    parser.parse.return_value.root_node = root
    get_parser = Mock(return_value=parser)
    monkeypatch.setattr(module, "get_parser", get_parser)

    result = module._binary_spans(source)

    assert result == {(20, 40)} | {(i, i + 2) for i, kind in enumerate(kinds) if kind in allowed}
    get_parser.assert_called_once_with(language)
    parser.parse.assert_called_once_with(source.source)


def test_binary_spans_returns_empty_for_unary_expression(records, monkeypatch):
    source, _ = records(data=b"+b")
    root = SimpleNamespace(type="unary_operator", start_byte=0, end_byte=2, named_children=[])
    parser = Mock()
    parser.parse.return_value.root_node = root
    monkeypatch.setattr(module, "get_parser", Mock(return_value=parser))

    assert module._binary_spans(source) == set()


@pytest.mark.parametrize("boundary", ["get_parser", "parse"])
def test_binary_spans_propagates_parser_errors(records, monkeypatch, boundary):
    source, _ = records()
    error = RuntimeError("parser unavailable")
    parser = Mock()
    get_parser = Mock(return_value=parser)
    (get_parser if boundary == "get_parser" else parser.parse).side_effect = error
    monkeypatch.setattr(module, "get_parser", get_parser)

    with pytest.raises(RuntimeError) as caught:
        module._binary_spans(source)

    assert caught.value is error


@pytest.mark.parametrize("populated", [False, True])
def test_source_inventory_indexes_fresh_extraction_and_skips_empty_binary_scan(records, monkeypatch, populated):
    source, candidate = records()
    other = candidate.model_copy(update={"id": "candidate-2", "operator": "*"})
    candidates = [candidate, other] if populated else []
    read = Mock(return_value=source)
    extract = Mock(return_value=MutationCandidateAnalysis(candidates=candidates))
    binary = Mock(return_value={(0, len(source.source))})
    monkeypatch.setattr(module, "_read_source", read)
    monkeypatch.setattr(module, "extract_candidates", extract)
    monkeypatch.setattr(module, "_binary_spans", binary)

    actual_source, indexed, spans = module._source_inventory(ROOT, candidate)

    assert actual_source is source
    assert indexed == ({candidate.id: candidate, other.id: other} if populated else {})
    assert spans == ({(0, len(source.source))} if populated else set())
    read.assert_called_once_with(ROOT, candidate)
    extract.assert_called_once_with(source)
    if populated:
        binary.assert_called_once_with(source)
    else:
        binary.assert_not_called()


@pytest.mark.parametrize("boundary", ["_read_source", "extract_candidates", "_binary_spans"])
def test_source_inventory_does_not_turn_verification_failures_into_empty_inventory(records, monkeypatch, boundary):
    source, candidate = records()
    monkeypatch.setattr(module, "_read_source", Mock(return_value=source))
    monkeypatch.setattr(module, "extract_candidates", Mock(return_value=MutationCandidateAnalysis(candidates=[candidate])))
    monkeypatch.setattr(module, "_binary_spans", Mock(return_value=set()))
    error = ValueError("verification failed")
    monkeypatch.setattr(module, boundary, Mock(side_effect=error))

    with pytest.raises(ValueError) as caught:
        module._source_inventory(ROOT, candidate)

    assert caught.value is error


@pytest.mark.parametrize("field", [
    "id", "path", "language", "sourceHash", "kind", "operator", "originalText", "expressionText", "callable",
    *[f"{region}.{coordinate}" for region in ("span", "expressionSpan")
      for coordinate in ("startByte", "endByte", "startLine", "endLine", "startColumn", "endColumn")],
    "callable.name", "callable.span", "callable.originalText",
])
def test_candidate_edits_rejects_each_forged_dimension_even_with_no_rules(records, monkeypatch, field):
    source, candidate = records()
    data = candidate.model_dump()
    if "." in field:
        region, coordinate = field.split(".")
        value = data[region][coordinate]
        data[region][coordinate] = (
            value + 1 if isinstance(value, int) else
            span(1, 2).model_dump() if coordinate == "span" else "forged"
        )
    else:
        data[field] = {"kind": "comparison", "callable": None}.get(field, "forged")
    forged = MutationCandidate.model_validate(data)
    edits = Mock()
    verify = Mock()
    monkeypatch.setattr(module, "_edits", edits)
    monkeypatch.setattr(module, "_verify_replacement", verify)

    with pytest.raises(ValueError, match="^Stale or invalid mutation candidate:"):
        module._candidate_edits(forged, (source, {candidate.id: candidate}, set()), [])

    edits.assert_not_called()
    verify.assert_not_called()


@pytest.mark.parametrize("reject_second", [False, True])
def test_candidate_edits_accepts_equal_records_and_verifies_every_edit(records, monkeypatch, reject_second):
    source, candidate = records()
    fresh = MutationCandidate.model_validate(candidate.model_dump())
    manifests = [manifest_for(candidate, "-"), manifest_for(candidate, "*")]
    binary = {(0, len(source.source))}
    rules = ["arithmetic.add-to-subtract"]
    edits = Mock(return_value=manifests)
    error = ValueError("unsafe second replacement")
    verify = Mock(side_effect=[None, error] if reject_second else None)
    monkeypatch.setattr(module, "_edits", edits)
    monkeypatch.setattr(module, "_verify_replacement", verify)

    if reject_second:
        with pytest.raises(ValueError) as caught:
            module._candidate_edits(candidate, (source, {candidate.id: fresh}, binary), rules)
        assert caught.value is error
    else:
        assert module._candidate_edits(candidate, (source, {candidate.id: fresh}, binary), rules) == manifests

    edits.assert_called_once_with(candidate, rules, binary)
    assert verify.call_args_list == [call(source, manifest, candidate.kind) for manifest in manifests]


def test_candidate_edits_with_no_matching_rule_returns_no_edits(records, monkeypatch):
    source, candidate = records()
    verify = Mock()
    monkeypatch.setattr(module, "_verify_replacement", verify)

    binary = {(candidate.expressionSpan.startByte, candidate.expressionSpan.endByte)}
    assert module._candidate_edits(candidate, (source, {candidate.id: candidate}, binary), []) == []
    verify.assert_not_called()


@pytest.mark.parametrize(("data", "original", "replacement"), [
    ("é + b\r\n".encode(), "+", "≤"),
    ("é <= b\r\n".encode(), "<=", "<"),
    ("é < b\r\n".encode(), "<", "<="),
    (b"+ b", "+", "-"), ("é +".encode(), "+", "-"),
])
def test_verify_replacement_splices_utf8_bytes_and_preserves_source(records, monkeypatch, data, original, replacement):
    source, candidate = records(data=data, original=original)
    manifest = manifest_for(candidate, replacement)
    start = candidate.span.startByte
    site = candidate.model_copy(update={
        "id": "new-site", "sourceHash": "new-hash", "operator": replacement,
        "span": span(start, start + len(replacement.encode())),
    })
    extract = Mock(return_value=MutationCandidateAnalysis(candidates=[site]))
    monkeypatch.setattr(module, "extract_candidates", extract)

    assert module._verify_replacement(source, manifest, candidate.kind) is None

    modified = extract.call_args.args[0]
    assert modified == SourceFile(
        path=source.path, absolute_path=source.absolute_path, language=source.language,
        source=data[:start] + replacement.encode() + data[candidate.span.endByte:],
    )
    assert modified is not source
    assert source.source == data
    assert extract.call_count == 1


@pytest.mark.parametrize("mismatch", ["kind", "operator", "start", "end", "split", "empty"])
def test_verify_replacement_requires_one_site_matching_every_guard(records, monkeypatch, mismatch):
    source, candidate = records()
    manifest = manifest_for(candidate, "≤")
    start = candidate.span.startByte
    site = candidate.model_copy(update={"operator": "≤", "span": span(start, start + 3)})
    changes = {
        "kind": {"kind": "comparison"}, "operator": {"operator": "<"},
        "start": {"span": span(start - 1, start + 3)},
        "end": {"span": span(start, start + 1)},
    }
    sites = [] if mismatch == "empty" else [site.model_copy(update=changes.get(mismatch, {}))]
    if mismatch == "split":
        sites = [site.model_copy(update={"kind": "comparison"}), site.model_copy(update={"operator": "<"})]
    monkeypatch.setattr(module, "extract_candidates", Mock(return_value=MutationCandidateAnalysis(candidates=sites)))

    with pytest.raises(ValueError, match=f"^Unsafe mutation replacement: src/café.py:{start}:arithmetic.add-to-subtract$"):
        module._verify_replacement(source, manifest, candidate.kind)

    assert source.source == "é + b\r\n".encode()


@pytest.mark.parametrize(("data", "original", "replacement", "modified", "sites_kind", "sites_operator"), [
    (b"a+--b", "+", "-", b"a---b", "arithmetic", "--"),
    (b"a*/re/", "*", "/", b"a//re/", "condition", None),
])
def test_verify_replacement_rejects_lexical_collisions(records, monkeypatch, data, original, replacement, modified, sites_kind, sites_operator):
    source, candidate = records(data=data, original=original, language="javascript")
    manifest = manifest_for(candidate, replacement)
    collided_site = candidate.model_copy(update={"kind": sites_kind, "operator": sites_operator})
    extract = Mock(return_value=MutationCandidateAnalysis(candidates=[collided_site]))
    monkeypatch.setattr(module, "extract_candidates", extract)

    with pytest.raises(ValueError, match="^Unsafe mutation replacement:"):
        module._verify_replacement(source, manifest, candidate.kind)

    assert extract.call_args.args[0].source == modified
    assert source.source == data


def test_verify_replacement_searches_past_unrelated_sites(records, monkeypatch):
    source, candidate = records()
    manifest = manifest_for(candidate)
    matching = candidate.model_copy(update={"operator": "-"})
    monkeypatch.setattr(module, "extract_candidates", Mock(return_value=MutationCandidateAnalysis(
        candidates=[candidate, matching, candidate],
    )))

    assert module._verify_replacement(source, manifest, candidate.kind) is None


def test_verify_replacement_propagates_extractor_failure_without_changing_source(records, monkeypatch):
    source, candidate = records()
    original = source.source
    error = RuntimeError("extractor unavailable")
    monkeypatch.setattr(module, "extract_candidates", Mock(side_effect=error))

    with pytest.raises(RuntimeError) as caught:
        module._verify_replacement(source, manifest_for(candidate), candidate.kind)

    assert caught.value is error
    assert source.source == original
