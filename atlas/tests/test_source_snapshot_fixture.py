"""Loading shared projects must not apply universal-newline translation."""

import pytest

from tests.source_snapshot_fixture import case_bytes, case_sources, case_text


@pytest.mark.parametrize(
    "case_id",
    [
        "graph-source-spans-crlf-form-feed",
        "graph-source-spans-crlf-next-line",
        "graph-source-spans-crlf-line-separator",
    ],
)
def test_project_loading_preserves_source_bytes(case_id):
    expected = case_bytes("operational", case_id, "src/app.py")
    assert b"\r\n" in expected
    assert case_text("operational", case_id, "src/app.py").encode() == expected
    assert case_sources("operational", case_id)["src/app.py"].encode() == expected
