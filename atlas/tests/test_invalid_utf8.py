"""Malformed coffee bytes retain file identity but share decoded AST offsets."""

import hashlib
from pathlib import Path

import pytest

from atlas.parsing.discovery import SourceFile
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import FIXTURE_ROOT


VARIANT_ROOT = Path(__file__).parent / "fixtures/variants/operational/invalid-utf8"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            ("Report.ts", "typescript", "typescript/reporting/Report.ts", b"// tasting note: \xff\n",
            [
                ("Report", 76, 414), ("total", 93, 213), ("<anonymous>", 162, 204),
                ("render", 217, 412), ("<anonymous>", 293, 335),
            ],
            [
                ("reduce", 149, 208), ("portions", 183, 204), ("map", 283, 336),
                ("portions", 312, 333), ("join", 359, 376), ("total", 386, 405),
            ]),
            id="typescript",
        ),
        pytest.param(
            ("report.py", "python", "python/src/coffee/reporting/report.py", b"# tasting note: \xff\n",
            [("Report", 58, 392), ("total", 94, 189), ("render", 213, 392), ("render", 395, 463)],
            [
                ("sum", 145, 189), ("portions", 149, 170), ("join", 268, 329),
                ("portions", 287, 308), ("total", 371, 390), ("render", 443, 463),
            ]),
            id="python",
        ),
        pytest.param(
            ("report.go", "go", "go/reporting/report.go", b"// tasting note: \xff\n",
            [
                ("Report", 105, 138), ("Total", 140, 269), ("Render", 271, 547),
                ("Receipt", 549, 609), ("Preview", 684, 796),
            ],
            [
                ("Portions", 228, 249), ("make", 320, 349), ("len", 338, 348),
                ("append", 392, 458), ("Sprintf", 408, 457), ("Portions", 435, 456),
                ("Sprintf", 470, 545), ("Join", 504, 530), ("Total", 532, 544),
                ("Render", 592, 607), ("Receipt", 778, 794),
            ]),
            id="go",
        ),
        pytest.param(
            ("Report.java", "java", "java/reporting/Report.java", b"// tasting note: \xff\n",
            [
                ("coffee.reporting", 21, 46), ("Report", 138, 584), ("Report", 170, 189),
                ("total", 195, 310), ("render", 316, 582), ("<anonymous>", 423, 465),
            ],
            [
                ("sum", 256, 303), ("mapToInt", 256, 297), ("stream", 256, 270),
                ("portions", 280, 296), ("collect", 391, 512), ("map", 391, 466),
                ("stream", 391, 405), ("portions", 444, 465), ("joining", 488, 511),
                ("total", 563, 575),
            ]),
            id="java",
        ),
    ],
)
def test_original_file_digest_and_replacement_decoded_declarations(
    case: tuple[str, str, str, bytes, list[tuple[str, int, int]], list[tuple[str, int, int]]],
) -> None:
    name, language, original, prefix, symbol_spans, call_spans = case
    path = VARIANT_ROOT / name
    raw = path.read_bytes()
    assert raw == prefix + (FIXTURE_ROOT / original).read_bytes()
    decoded = raw.decode("utf-8", errors="replace").encode("utf-8")
    assert decoded == raw.replace(b"\xff", b"\xef\xbf\xbd")
    assert len(decoded) == len(raw) + 2
    source = SourceFile(name, path, language, raw)
    repository = parse_files([source])
    assert len(repository.files) == 1
    file = repository.files[0]
    assert file.source is source
    assert file.source.path == name
    assert file.source.absolute_path == path
    assert file.parse_error is None
    assert file.content_hash == hashlib.sha256(raw).hexdigest()
    assert file.content_hash != hashlib.sha256(decoded).hexdigest()
    assert [(s.name, s.start_byte, s.end_byte) for s in file.symbols] == symbol_spans
    assert [(c.name, c.start_byte, c.end_byte) for c in file.calls] == call_spans
    for call in file.calls:
        assert call.evidence == decoded[call.start_byte:call.end_byte].decode("utf-8")
        assert call.line == decoded.count(b"\n", 0, call.start_byte) + 1
    assert source.source == raw
    assert path.read_bytes() == raw
