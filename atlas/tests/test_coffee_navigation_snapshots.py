"""Complete graph CLI responses from the eight production-indexed coffee samples."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tests.coffee_fixture import LANGUAGES
from tests.coffee_navigation import NAVIGATION_SNAPSHOT_ROOT, navigation_responses, normalize_responses


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_navigation_matches_snapshot(language: str, tmp_path: Path) -> None:
    actual = navigation_responses(language, tmp_path / "atlas.sqlite")
    expected = json.loads((NAVIGATION_SNAPSHOT_ROOT / f"{language}-coffee.json").read_text(encoding="utf-8"))
    assert actual == expected


@pytest.mark.parametrize("field", ["repositoryId", "graphRevision", "indexedAt"])
def test_normalization_rejects_inconsistent_metadata(field: str) -> None:
    response = {"repositoryId": "repo", "graphRevision": "revision", "indexedAt": "timestamp"}
    other = {**response, field: "different"}
    with pytest.raises(AssertionError, match=field):
        normalize_responses({"overview": response, "source": other}, Path("/checkout/python"))


def test_normalization_preserves_nonvolatile_content_and_order() -> None:
    responses = {"context": {
        "repositoryId": "repo", "graphRevision": "revision", "indexedAt": "timestamp",
        "root": "/checkout/python", "absolutePath": "/checkout/python/report.py",
        "nodes": [{"stableKey": "z"}, {"stableKey": "a"}],
        "edges": [{"evidence": "render()", "confidence": "INFERRED", "ordinal": 7}],
        "diagnostics": [{"path": "report.py", "message": "warning"}],
        "filters": {"relations": ["CALLS"]}, "boundaries": [{"reason": "depth"}],
        "truncated": True, "source": {"status": "ok", "lines": ["def render():", "    return 1"]},
    }}
    before = deepcopy(responses)
    expected = deepcopy(responses)
    expected["context"].update(repositoryId="<repository-id>", graphRevision="<graph-revision>",
                               indexedAt="<indexed-at>", root="/samples/coffee/python",
                               absolutePath="/samples/coffee/python/report.py")
    assert normalize_responses(responses, Path("/checkout/python")) == expected
    assert responses == before
