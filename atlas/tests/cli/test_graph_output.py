"""Check CLI projections and source text against navigation payload contracts."""

from copy import deepcopy
import json

import pytest

from atlas.cli.graph_output import graph_output
from atlas.cli.graph_source_output import excerpt_text, source_text


def test_recursive_projection_preserves_indexed_facts_and_input():
    node = {"stableKey": "external:café", "level": "external", "type": "external",
            "qualifiedName": "external:café", "external": True, "path": None,
            "parentStableKey": None, "name": "café", "startLine": None}
    payload = {
        "repositoryId": "coffee", "graphRevision": "rev-1", "indexedAt": None,
        "filters": {"key": "external:café", "relations": ["CALLS"]},
        "node": node, "ancestors": [], "nested": [{"nodes": [node]}],
        "edges": [{"sourceStableKey": "brew", "targetStableKey": "external:café", "type": "CALLS"}],
        "boundaries": [{"stableKey": "external:café", "reason": "external_unresolved_or_ambiguous", "expandable": False}],
        "diagnostics": [{"message": "external:café", "level": "warning"}],
        "diagnosticsTruncated": False,
    }
    original = deepcopy(payload)
    projected = {**node, "level": "unresolved", "type": "unresolved", "qualifiedName": "unresolved:café",
                 "external": False, "unresolved": True}

    result = graph_output(payload)

    assert result == {**payload, "node": projected, "nested": [{"nodes": [projected]}],
                      "boundaries": [{"stableKey": "external:café", "reason": "unresolved_or_ambiguous", "expandable": False}]}
    assert payload == original
    assert result is not payload
    assert result["node"] is not node
    assert graph_output(result) == result


@pytest.mark.parametrize(("value", "expected"), [
    (None, None), (False, False), (42, 42), ("external:brew", "external:brew"),
    ([], []), ({}, {}),
    ({"level": "external"}, {"level": "unresolved"}),
    ({"level": "external", "qualifiedName": "external:brew", "external": True},
     {"level": "unresolved", "qualifiedName": "external:brew", "external": True}),
    ({"reason": "external_unresolved_or_ambiguous"}, {"reason": "unresolved_or_ambiguous"}),
    ({"reason": "depth_limit"}, {"reason": "depth_limit"}),
    ({"level": "function", "stableKey": "external:brew", "qualifiedName": "external:brew", "external": False},
     {"level": "function", "stableKey": "external:brew", "qualifiedName": "external:brew", "external": False}),
])
def test_projection_only_changes_recognized_labels(value, expected):
    assert graph_output(value) == expected


@pytest.mark.parametrize("identity", [
    {}, {"qualifiedName": None}, {"qualifiedName": 123}, {"qualifiedName": "brew"},
    {"qualifiedName": "module.external:brew"}, {"qualifiedName": "external:external:brew"},
])
def test_unresolved_identity_handles_optional_qualified_name(identity):
    node = {"stableKey": "external:brew", "level": "external", "type": "external", **identity}
    expected = {**node, "level": "unresolved", "type": "unresolved", "external": False, "unresolved": True}
    if identity.get("qualifiedName") == "external:external:brew":
        expected["qualifiedName"] = "unresolved:external:brew"
    assert graph_output(node) == expected


def test_single_source_text_preserves_metadata_and_numbering():
    metadata = {"repositoryId": "coffee", "graphRevision": "rev-1", "indexedAt": None,
                "filters": {"key": "brew", "maxLines": 3, "startLine": 12},
                "diagnostics": [{"message": "café"}], "diagnosticsTruncated": True}
    excerpt = {"status": "ok", "path": "café.py", "startLine": 12, "endLine": 14,
               "lines": ["def café():", "", "    return 1"], "truncated": True, "nextStartLine": 15}
    payload = {**metadata, "source": excerpt}
    original = deepcopy(payload)

    result = source_text(payload)

    metadata_text, excerpt_block = result.split("\n\n", 1)
    header, details, *lines = excerpt_block.splitlines()
    assert json.loads(metadata_text) == metadata
    assert header == "### café.py"
    assert json.loads(details) == {"stableKey": "brew", **{key: value for key, value in excerpt.items() if key != "lines"}}
    assert lines == ["12: def café():", "13: ", "14:     return 1"]
    assert "café" in result
    assert payload == original


def test_multiple_source_text_preserves_order_statuses_and_metadata():
    metadata = {"repositoryId": "coffee", "graphRevision": "rev-1",
                "filters": {"keys": ["brew", "external:serve", "missing"]},
                "diagnostics": [], "diagnosticsTruncated": False}
    excerpts = [
        {"stableKey": "brew", "status": "ok", "path": "coffee.py", "startLine": 5,
         "endLine": 5, "lines": ["brew()"], "truncated": False, "nextStartLine": None},
        {"stableKey": "external:serve", "status": "unavailable"},
        {"stableKey": "missing", "status": "missing", "path": "gone.py"},
    ]
    payload = {**metadata, "sources": excerpts}
    original = deepcopy(payload)

    sections = source_text(payload).split("\n\n")

    assert json.loads(sections[0]) == metadata
    assert len(sections) == 4
    for section, excerpt in zip(sections[1:], excerpts):
        header, details, *lines = section.splitlines()
        assert header == f"### {excerpt.get('path', excerpt['stableKey'])}"
        expected_details = excerpt.copy()
        expected_details.pop("lines", None)
        assert json.loads(details) == expected_details
        assert lines == (["5: brew()"] if excerpt["status"] == "ok" else [])
    assert payload == original


@pytest.mark.parametrize("status", [
    "unavailable", "unverified", "changed", "unsupported_encoding", "span_unavailable",
    "unsafe", "missing", "unreadable", "too_large",
])
def test_status_only_source_text_does_not_invent_lines(status):
    excerpt = {"status": status, "path": "coffee.py"}
    if status == "too_large":
        excerpt.update(maxFileBytes=8388608, maxExcerptBytes=16384)
    payload = {"filters": {"key": "brew"}, "source": excerpt}
    metadata, block = source_text(payload).split("\n\n")
    assert json.loads(metadata) == {"filters": {"key": "brew"}}
    header, details = block.splitlines()
    assert header == "### coffee.py"
    assert json.loads(details) == {"stableKey": "brew", **excerpt}


def test_empty_sources_render_only_metadata():
    assert source_text({"filters": {"keys": []}, "sources": []}) == '{"filters": {"keys": []}}'


def test_excerpt_numbering_defaults_to_one_and_keeps_blank_lines():
    excerpt = {"stableKey": "brew", "status": "ok", "lines": ["", "café()"]}
    assert excerpt_text(excerpt) == '### brew\n{"stableKey": "brew", "status": "ok"}\n1: \n2: café()'


def test_empty_verified_excerpt_keeps_navigation_details():
    excerpt = {"stableKey": "brew", "status": "ok", "path": "coffee.py", "startLine": 10,
               "endLine": 9, "lines": [], "truncated": False, "nextStartLine": None}
    header, details = excerpt_text(excerpt).splitlines()
    assert header == "### coffee.py"
    assert json.loads(details) == {key: value for key, value in excerpt.items() if key != "lines"}
