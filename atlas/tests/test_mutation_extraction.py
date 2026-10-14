"""Extraction contract coverage against original-byte code samples."""

import hashlib
from pathlib import Path

import pytest

from atlas.parsing.mutation import extract_mutation_sites

FIXTURES = Path(__file__).parent / "fixtures" / "mutation"


def sample(suffix: str, language: str, *, crlf: bool = False):
    source = (FIXTURES / f"conditions.{suffix}").read_bytes()
    if crlf:
        source = source.replace(b"\n", b"\r\n")
    return source, extract_mutation_sites(f"samples/conditions.{suffix}", language, source)


def expressions(result):
    return [(site.kind, site.expression) for site in result.sites]


@pytest.mark.parametrize("language", ["python", "javascript", "typescript", "tsx"])
def test_runtime_interpolation_byte_spans_and_context(language):
    suffix = "py" if language == "python" else "js"
    source = (FIXTURES / f"interpolations.{suffix}").read_bytes()
    result = extract_mutation_sites(f"interpolations.{suffix}", language, source)
    regions = {region.identity: region for region in result.callables}
    for site in result.sites:
        assert_original_site(source, site)
        assert_callable_context(source, site, regions)


def assert_byte_position(source, position):
    byte, line, column = position
    assert line == source[:byte].count(b"\n") + 1
    assert column == byte - source.rfind(b"\n", 0, byte)


def assert_original_site(source, site):
    span = site.span
    assert source[span.start_byte:span.end_byte].decode() == site.expression
    assert site.original_file_hash == hashlib.sha256(source).hexdigest()
    assert site.diff_relationship == "folder-scope"
    assert len(site.site_id) == 64
    assert_byte_position(source, (span.start_byte, span.start_line, span.start_column))
    assert_byte_position(source, (span.end_byte, span.end_line, span.end_column))


@pytest.mark.parametrize("suffix,language", [
    ("py", "python"), ("js", "javascript"), ("ts", "typescript"), ("tsx", "tsx"),
])
@pytest.mark.parametrize("crlf", [False, True])
def test_original_byte_spans_hashes_and_determinism(suffix, language, crlf):
    source, result = sample(suffix, language, crlf=crlf)
    path = f"samples/conditions.{suffix}"
    assert result == extract_mutation_sites(f"samples/./conditions.{suffix}", language, source)
    assert result == extract_mutation_sites(f"./{path}", language, source)
    assert len({site.site_id for site in result.sites}) == len(result.sites)
    regions = {region.identity: region for region in result.callables}
    for site in result.sites:
        assert_original_site(source, site)
        assert_callable_context(source, site, regions)
    edited = extract_mutation_sites(path, language, source + b"\n")
    assert {site.site_id for site in result.sites}.isdisjoint(site.site_id for site in edited.sites)
    moved = extract_mutation_sites("other/path", language, source)
    assert {site.site_id for site in result.sites}.isdisjoint(site.site_id for site in moved.sites)


def assert_callable_context(source, site, regions):
    assert site.expression in site.context
    if site.callable is None:
        return
    region = regions[site.callable]
    assert region.start_byte <= site.span.start_byte < site.span.end_byte <= region.end_byte
    assert site.context == source[region.start_byte:region.end_byte].decode("utf-8")


def test_unicode_byte_columns_multiline_and_raw_file_hash():
    source = 'if café == "🫘" and (\n    café != "☕"\n): pass\n'.encode()
    result = extract_mutation_sites("unicode.py", "python", source)
    assert result.diagnostics == []
    assert len(result.sites) == 4
    inner = next(site for site in result.sites if site.expression == 'café != "☕"')
    assert inner.span.start_line == inner.span.end_line == 2
    assert inner.span.start_column == 5
    assert inner.span.end_column == 5 + len(inner.expression.encode())
    predicate = next(site for site in result.sites if site.kind == "predicate")
    assert predicate.span.start_line == 1 and predicate.span.end_line == 3
    assert predicate.original_file_hash == hashlib.sha256(source).hexdigest()


@pytest.mark.parametrize("language", ["ruby", "go", "Python", ""])
def test_unsupported_language_is_diagnostic(language):
    result = extract_mutation_sites("sample", language, b"if value: pass")
    assert not result.sites and not result.callables
    assert [d.code for d in result.diagnostics] == ["unsupported-language"]


def test_invalid_encoding_is_diagnostic():
    result = extract_mutation_sites("sample.py", "python", b"if value: pass\n#\xff")
    assert not result.sites and not result.callables
    assert [d.code for d in result.diagnostics] == ["invalid-encoding"]


@pytest.mark.parametrize("language,source", [
    ("python", b"if broken > : pass\nif healthy > 0: pass\n"),
    ("javascript", b"if (broken > ) {}\nif (healthy > 0) {}\n"),
    ("typescript", b"if (broken > ) {}\nif (healthy > 0) {}\n"),
    ("tsx", b"if (broken > ) {}\nif (healthy > 0) {}\n"),
])
def test_recovery_regions_are_diagnosed_and_skipped(language, source):
    result = extract_mutation_sites("broken", language, source)
    assert "parse-error" in [d.code for d in result.diagnostics]
    assert all("broken" not in site.expression for site in result.sites)
    assert ("comparison", "healthy > 0") in expressions(result)


@pytest.mark.parametrize("language", ["python", "javascript", "typescript", "tsx"])
def test_valid_empty_file_is_success(language):
    result = extract_mutation_sites("empty", language, b"")
    assert result.sites == result.callables == result.diagnostics == []
