"""Independent mutation planning, verified against original on-disk bytes."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from atlas.domain.models import SourceFile
from atlas.domain.mutation_candidates import MutationCandidate
from atlas.mutations import REGISTRY, generate_manifests
from atlas.parsing.mutation_candidates import extract_candidates

ADD = {"arithmetic.add-to-subtract": ["-"]}


def candidates(file: Path, text: str, language: str = "python") -> list[MutationCandidate]:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(text.encode("utf-8"))
    return extract_candidates(SourceFile(path=file.name, absolute_path=file, language=language, source=file.read_bytes())).candidates


def test_identity_order_dedup_and_no_writes(tmp_path: Path) -> None:
    first = candidates(tmp_path / "sample.py", "x = a + b * c\n")
    other = tmp_path / "nested/other.py"
    other.parent.mkdir()
    other.write_text("x = a + b\n")
    second = extract_candidates(SourceFile(path="nested/other.py", absolute_path=other, language="python", source=other.read_bytes())).candidates
    selected = {**ADD, "arithmetic.multiply-to-divide": ["/"]}
    result = generate_manifests(tmp_path, first + second, selected)
    assert result == generate_manifests(tmp_path, list(reversed(first + second)) * 2, dict(reversed(list(selected.items()))))
    assert len(result) == 3
    assert len({item.id for item in result}) == 3
    for item in result:
        payload = item.model_dump(exclude={"id"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert item.id == hashlib.sha256(canonical.encode()).hexdigest()
        assert base64.b64decode(item.originalBytes) == item.originalText.encode()
        assert base64.b64decode(item.replacementBytes) == item.replacement.encode()
    assert (tmp_path / "sample.py").read_bytes() == b"x = a + b * c\n"
    assert generate_manifests(tmp_path, first, {}) == []
    assert generate_manifests(tmp_path, first, {"arithmetic.add-to-subtract": []}) == []
    assert generate_manifests(tmp_path, [], ADD) == []


def test_identity_captures_source_not_only_edit(tmp_path: Path) -> None:
    first = generate_manifests(tmp_path, candidates(tmp_path / "sample.py", "x = a + 1\n"), ADD)[0]
    second = generate_manifests(tmp_path, candidates(tmp_path / "sample.py", "x = a + 2\n"), ADD)[0]
    assert first.span == second.span
    assert first.originalText == second.originalText
    assert first.replacement == second.replacement
    assert first.sourceHash != second.sourceHash
    assert first.candidateId != second.candidateId
    assert first.id != second.id


def test_unicode_crlf_and_chain_are_token_local(tmp_path: Path) -> None:
    extracted = candidates(tmp_path / "sample.py", "# café\r\nif 0 < é < 3:\r\n x = é + 1\r\n")
    result = generate_manifests(tmp_path, extracted, {**ADD, "comparison.less-to-less-equal": ["<="]})
    assert [item.originalText for item in result] == ["<", "<", "+"]
    assert [item.span.startLine for item in result] == [2, 2, 3]
    assert result[1].span.startColumn == 11  # one-based UTF-8 byte column
    data = (tmp_path / "sample.py").read_bytes()
    for item in result:
        assert data[item.span.startByte:item.span.endByte] == base64.b64decode(item.originalBytes)


@pytest.mark.parametrize(("language", "text"), [
    ("python", "x = +a + (b * c)\n"),
    ("javascript", "const x = +a + (b * c);"),
    ("typescript", "const x = +a + (b * c);"),
    ("tsx", "const x = <b>{+a + (b * c)}</b>;"),
    ("java", "class A { int x = +a + (b * c); }"),
    ("kotlin", "fun f(){ val x = +a + (b * c) }"),
    ("rust", "fn f(){let x = a + (b * c);}"),
    ("go", "package p\nfunc f(){x := +a + (b * c)}"),
    ("elixir", "x = +a + (b * c)"),
])
def test_binary_only_all_languages(tmp_path: Path, language: str, text: str) -> None:
    extracted = candidates(tmp_path / "sample.py", text, language)
    result = generate_manifests(tmp_path, extracted, {**ADD, "arithmetic.multiply-to-divide": ["/"]})
    assert [item.originalText for item in result] == ["+", "*"]
    # Nested expression spans overlap, but each manifest is a standalone edit.
    assert len({item.id for item in result}) == 2


def test_unary_with_comments_not_text_heuristics(tmp_path: Path) -> None:
    extracted = candidates(tmp_path / "sample.py", "x = ( # binary? a + b\n +a)\ny = a + +b\n")
    result = generate_manifests(tmp_path, extracted, ADD)
    assert len(result) == 1
    assert result[0].span.startLine == 3


def test_strict_loose_logical_assignment_are_separate(tmp_path: Path) -> None:
    extracted = candidates(tmp_path / "sample.py", "if (a == b && a === b) { x += 1; }", "javascript")
    result = generate_manifests(tmp_path, extracted, {
        "comparison.equal-to-not-equal": ["!="],
        "comparison.strict-equal-to-strict-not-equal": ["!=="],
        "logical.and-to-or": ["||"],
        "assignment.add-to-subtract": ["-="],
    })
    assert [(item.originalText, item.replacement) for item in result] == [("==", "!="), ("&&", "||"), ("===", "!=="), ("+=", "-=")]
    assert generate_manifests(tmp_path, extracted, ADD) == []
    extracted = candidates(tmp_path / "sample.py", "x = a and b\ny = a && b", "elixir")
    result = generate_manifests(tmp_path, extracted, {"logical.strict-and-to-or": ["or"], "logical.truthy-and-to-or": ["||"]})
    assert [(item.originalText, item.replacement) for item in result] == [("and", "or"), ("&&", "||")]
    assert generate_manifests(tmp_path, extracted, {"logical.and-to-or": ["||"]}) == []


@pytest.mark.parametrize(("language", "text"), [
    ("python", "for x in values:\n if x is not None and x not in other:\n  pass\n"),
    ("rust", "fn f(){ custom!(a + b); if let Some(x) = a {} }"),
    ("kotlin", "fun f(){ if (a === b) {} }"),
])
def test_unlisted_constructs_have_no_replacements(tmp_path: Path, language: str, text: str) -> None:
    extracted = candidates(tmp_path / "sample.py", text, language)
    rules = {rule.id: sorted({mapping.replacement for mapping in rule.mappings})
             for rule in REGISTRY
             if rule.kind != "logical"}
    assert generate_manifests(tmp_path, extracted, rules) == []


@pytest.mark.parametrize("field", ["id", "sourceHash", "originalText", "expressionText", "operator", "language", "kind", "span", "expressionSpan", "callable"])
def test_reject_forged_candidates(tmp_path: Path, field: str) -> None:
    extracted = candidates(tmp_path / "sample.py", "def f(a):\n return a + 1\n")
    item = next(item for item in extracted if item.operator == "+")
    changes: dict[str, object] = {
        "id": "0" * 64, "sourceHash": "0" * 64, "originalText": "-",
        "expressionText": "a + 2", "operator": "-", "language": "unknown",
        "kind": "assignment", "span": item.span.model_copy(update={"startColumn": 999}),
        "expressionSpan": item.expressionSpan.model_copy(update={"endByte": 999}), "callable": None,
    }
    forged = item.model_copy(update={field: changes[field]})
    with pytest.raises(ValueError, match="Stale or invalid"):
        generate_manifests(tmp_path, [forged], {})


@pytest.mark.parametrize("data", [b"x = a + 2\n", b"\xff", b"x = ("])
def test_reject_stale_even_without_selected_rules(tmp_path: Path, data: bytes) -> None:
    extracted = candidates(tmp_path / "sample.py", "x = a + 1\n")
    (tmp_path / "sample.py").write_bytes(data)
    with pytest.raises(ValueError):
        generate_manifests(tmp_path, extracted, {})


@pytest.mark.parametrize("path", ["../outside.py", "/tmp/outside.py", "nested/../../outside.py", "./sample.py", "missing.py"])
def test_reject_unsafe_paths(tmp_path: Path, path: str) -> None:
    item = candidates(tmp_path / "sample.py", "x = a + 1\n")[0].model_copy(update={"path": path})
    with pytest.raises(ValueError):
        generate_manifests(tmp_path, [item], ADD)


@pytest.mark.parametrize("case", [
    ("javascript", "let x = a+--b;", ADD),
    ("javascript", "let x = a*/b/.test(c);", {"arithmetic.multiply-to-divide": ["/"]}),
    ("rust", "fn f(){let x = a**b;}", {"arithmetic.multiply-to-divide": ["/"]}),
])
def test_reject_retokenized_replacements(tmp_path: Path, case: tuple[str, str, dict[str, list[str]]]) -> None:
    language, text, rules = case
    extracted = candidates(tmp_path / "sample.py", text, language)
    assert extracted
    with pytest.raises(ValueError, match="Unsafe mutation replacement"):
        generate_manifests(tmp_path, extracted, rules)
    assert (tmp_path / "sample.py").read_text() == text


def test_reject_external_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    extracted = candidates(tmp_path / "sample.py", "x = a + 1\n")
    (root / "sample.py").symlink_to(tmp_path / "sample.py")
    with pytest.raises(ValueError, match="escapes root"):
        generate_manifests(root, extracted, ADD)
