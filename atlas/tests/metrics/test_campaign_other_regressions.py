"""Graph boundaries and literal Markdown from campaign survivors."""

from collections import deque

import pytest

from atlas.metrics.cycles import _CycleSearch, circular_dependencies
from atlas.metrics.report_markdown import code, location
from atlas.metrics.resolver import _language_family


@pytest.mark.parametrize("language,expected", [("typescript", "javascript"), ("c", "c")])
def test_language_family_uses_adapter_or_language_fallback(language, expected):
    assert _language_family(language) == expected


@pytest.mark.parametrize("external", [{"type": "external"}, {"type": "file", "level": "external"}])
def test_either_external_marker_excludes_file_owner(external):
    nodes: list[dict[str, object]] = [{"stableKey": "a", "type": "file"}, {"stableKey": "b", **external}]
    edges: list[dict[str, object]] = [{"type": "IMPORTS", "sourceStableKey": a, "targetStableKey": b} for a, b in [("a", "b"), ("b", "a")]]
    assert circular_dependencies(nodes, edges) == {"version": 1, "groups": []}


@pytest.mark.parametrize("source,target", [("a", "missing"), ("missing", "a")])
def test_one_missing_import_endpoint_is_ignored(source, target):
    nodes: list[dict[str, object]] = [{"stableKey": "a", "type": "file"}]
    edges: list[dict[str, object]] = [{"type": "IMPORTS", "sourceStableKey": source, "targetStableKey": target}]
    assert circular_dependencies(nodes, edges)["groups"] == []


def test_representative_cycle_skips_self_outside_and_seen_neighbors():
    # a->a must not hide a multi-file cycle; x is outside its component.
    adjacency = {"a": ["a", "b"], "b": ["c", "x"], "c": ["a", "b"], "x": []}
    nodes: list[dict[str, object]] = [{"stableKey": key, "type": "file"} for key in adjacency]
    edges: list[dict[str, object]] = [{"type": "IMPORTS", "sourceStableKey": a, "targetStableKey": b}
             for a, targets in adjacency.items() for b in targets]
    groups = circular_dependencies(nodes, edges)["groups"]
    assert len(groups) == 1
    assert groups[0]["nodeStableKeys"] == ["a", "b", "c"]
    assert groups[0]["exampleCycle"] == ["a", "b", "c", "a"]


def test_cycle_search_does_not_reparent_seen_or_queue_outside_neighbors():
    search = _CycleSearch({"b": ["b", "outside", "c"]}, {"a", "b", "c"},
                          "a", {"b": None}, deque())
    assert not search.visit_neighbors("b")
    assert search.parents == {"b": None, "c": "b"}
    assert list(search.pending) == ["c"]


@pytest.mark.parametrize("value,expected", [("`start", "`` `start ``"), ("end`", "`` end` ``")])
def test_one_sided_backtick_padding(value, expected):
    assert code(value) == expected


@pytest.mark.parametrize("node,expected", [({"path": "a.py"}, "a.py"), ({"path": "", "line": 0}, "Unknown file:0"), ({}, "Unknown file")])
def test_location_path_fallback(node, expected):
    assert location(node) == expected
