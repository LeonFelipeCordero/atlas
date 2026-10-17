"""In-memory artifact assembly, level projection, and snapshot validation."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from atlas.domain.models import Complexity, ParsedRepository
from atlas.metrics import artifact
from atlas.metrics.resolver import Connection, ExternalNode, ResolvedGraph
from tests.metrics.metric_core_support import edge, graph_node, parsed_file, symbol


@pytest.fixture
def extraction(monkeypatch: pytest.MonkeyPatch) -> Mock:
    extract = Mock(return_value=SimpleNamespace(candidates=[]))
    monkeypatch.setattr(artifact, "extract_candidates", extract)
    return extract


@pytest.fixture
def empty_artifact(extraction) -> artifact.GraphArtifact:
    return artifact.build_artifact(Path("/repo"), ParsedRepository([]), ResolvedGraph([], []))


def test_empty_repository_has_root_module_stats_views_and_utc_metadata(extraction, monkeypatch) -> None:
    now = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    clock = Mock()
    clock.now.return_value = now
    monkeypatch.setattr(artifact, "datetime", clock)

    result = artifact.build_artifact(Path("/repo"), ParsedRepository([]), ResolvedGraph([], []))

    assert result.schemaVersion == 2
    assert result.repository == {"path": "/repo", "name": "repo", "indexedAt": now.isoformat(), "languages": []}
    clock.now.assert_called_once_with(timezone.utc)
    assert result.stats == {"files": 0, "symbols": 0, "modules": 1, "types": 0, "callables": 0,
                            "nodes": 2, "edges": 1, "externalNodes": 0, "parseErrors": 0}
    assert result.views == {"module": {"nodes": ["module:."], "edges": []},
                            **{level: {"nodes": [], "edges": []} for level in ("file", "type", "callable")}}
    assert [(n["stableKey"], n["depth"], n["ancestorStableKeys"]) for n in result.nodes] == [
        ("repository", 0, []), ("module:.", 1, ["repository"]),
    ]
    assert result.edges == [{
        "sourceStableKey": "repository", "targetStableKey": "module:.", "type": "CONTAINS",
        "confidence": "EXTRACTED", "path": ".", "line": 1, "evidence": None,
        "sourceType": "repository", "sourceKind": "repository", "sourceLevel": "repository",
        "targetType": "module", "targetKind": "directory", "targetLevel": "module",
    }]
    assert (result.diagnostics, result.circularDependencies, result.mutationCandidates) == (
        [], {"version": 1, "groups": []}, [],
    )
    extraction.assert_not_called()


@pytest.mark.parametrize(("source", "lines"), [(b"", 0), (b"a", 1), (b"a\n", 1),
                                                (b"a\nb", 2), (b"\n\n", 2), ("é".encode(), 1)])
def test_file_counts_bytes_and_unterminated_final_lines(extraction, source: bytes, lines: int) -> None:
    file = parsed_file(source=source)

    result = artifact.build_artifact(Path("/repo"), ParsedRepository([file]), ResolvedGraph([], []))

    file_node = next(n for n in result.nodes if n["level"] == "file")
    assert file_node == {
        "stableKey": "file:src/a.py", "type": "file", "kind": "file", "level": "file",
        "language": "python", "name": "a.py", "qualifiedName": "src/a.py", "path": "src/a.py",
        "parentStableKey": "module:src", "depth": 3,
        "ancestorStableKeys": ["repository", "module:.", "module:src"],
        "properties": {"bytes": len(source), "lineCount": lines, "sha256": "digest",
                       "fanIn": 0, "fanOut": 0, "transitiveChangeImpact": 0, "instability": None},
    }
    extraction.assert_called_once_with(file.source)


def test_directory_ancestors_are_unique_parent_first_and_named_by_path(extraction) -> None:
    files = [parsed_file(path) for path in ("z/q/a.py", "a/b.py", "z/q/c.py", "root.py")]

    result = artifact.build_artifact(Path("/repo"), ParsedRepository(files), ResolvedGraph([], []))

    assert [(n["stableKey"], n["name"], n["qualifiedName"], n["parentStableKey"])
            for n in result.nodes if n["level"] == "module"] == [
        ("module:.", "repo", "repo", "repository"),
        ("module:a", "a", "a", "module:."),
        ("module:z", "z", "z", "module:."),
        ("module:z/q", "q", "z.q", "module:z"),
    ]


@pytest.mark.parametrize(("kind", "level"), [
    *[(kind, "module") for kind in ("module", "namespace", "package")],
    *[(kind, "type") for kind in ("class", "enum", "interface", "struct", "trait", "type")],
    *[(kind, "callable") for kind in ("constructor", "function", "method", "procedure")],
    ("variable", "symbol"),
])
def test_symbol_kind_maps_to_level_and_preserves_source_metadata(extraction, kind, level) -> None:
    record = symbol(kind=kind, decorators=["cached"], line_count=3, parameter_count=2,
                    complexity=Complexity(3, 1, 2, 6, 3))

    result = artifact.build_artifact(Path("/repo"), ParsedRepository([parsed_file(symbols=[record])]), ResolvedGraph([], []))

    actual = next(n for n in result.nodes if n["stableKey"] == "fn")
    metrics = {} if level == "symbol" else {"fanIn": 0, "fanOut": 0, "transitiveChangeImpact": 0, "instability": None}
    assert actual == {
        "stableKey": "fn", "type": kind, "kind": kind, "level": level, "language": "python",
        "name": "brew", "qualifiedName": "a.brew", "path": "src/a.py", "parentStableKey": "file:src/a.py",
        "startLine": 2, "startColumn": 1, "endLine": 5, "endColumn": 1, "signature": "brew()",
        "depth": 4, "ancestorStableKeys": ["repository", "module:.", "module:src", "file:src/a.py"],
        "properties": {"visibility": "public", "decorators": ["cached"], "lineCount": 3, "parameterCount": 2,
                       "baseCyclomaticComplexity": 3, "nestedCyclomaticComplexity": 1,
                       "loopNestedComplexity": 2, "cyclomaticComplexity": 6, "maxDecisionDepth": 3, **metrics},
    }
    assert result.edges[-1]["evidence"] == "file:src/a.py contains brew"


def test_unmeasured_symbols_omit_optional_metric_properties(extraction) -> None:
    result = artifact.build_artifact(Path("/repo"), ParsedRepository([
        parsed_file(symbols=[symbol(kind="variable")]),
    ]), ResolvedGraph([], []))

    assert result.nodes[-1]["properties"] == {"visibility": "public", "decorators": []}


def test_resolved_edges_external_nodes_diagnostics_and_mutation_candidates(extraction) -> None:
    files = [parsed_file(parse_error="syntax error"), parsed_file("b.py", source=b"b")]
    candidate_a = Mock()
    candidate_a.model_dump.return_value = {"id": "a"}
    candidate_b = Mock()
    candidate_b.model_dump.return_value = {"id": "b"}
    extraction.side_effect = [SimpleNamespace(candidates=[candidate_a]), SimpleNamespace(candidates=[candidate_b])]
    graph = ResolvedGraph([
        Connection("file:src/a.py", "ext", "IMPORTS", "INFERRED", "src/a.py", 2, "import os", True),
        Connection("file:src/a.py", "file:b.py", "IMPORTS", "EXTRACTED", "src/a.py", 3, None),
    ], [ExternalNode("ext", "python", "module", "os.path")])

    result = artifact.build_artifact(Path("/repo"), ParsedRepository(files), graph)

    assert result.stats == {"files": 2, "symbols": 0, "modules": 2, "types": 0, "callables": 0,
                            "nodes": 6, "edges": 6, "externalNodes": 1, "parseErrors": 1}
    assert result.nodes[-1] == {
        "stableKey": "ext", "type": "external", "kind": "module", "level": "external", "language": "python",
        "name": "path", "qualifiedName": "external:python:os.path", "path": None,
        "parentStableKey": "repository", "properties": {}, "depth": 1, "ancestorStableKeys": ["repository"],
    }
    assert result.edges[-2:] == [
        {"sourceStableKey": "file:src/a.py", "targetStableKey": "ext", "type": "IMPORTS", "confidence": "INFERRED",
         "path": "src/a.py", "line": 2, "evidence": "import os", "typeOnly": True,
         "sourceType": "file", "sourceKind": "file", "sourceLevel": "file",
         "targetType": "external", "targetKind": "module", "targetLevel": "external"},
        {"sourceStableKey": "file:src/a.py", "targetStableKey": "file:b.py", "type": "IMPORTS", "confidence": "EXTRACTED",
         "path": "src/a.py", "line": 3, "evidence": None,
         "sourceType": "file", "sourceKind": "file", "sourceLevel": "file",
         "targetType": "file", "targetKind": "file", "targetLevel": "file"},
    ]
    assert result.diagnostics == [{"severity": "error", "path": "src/a.py", "language": "python", "message": "syntax error"}]
    assert result.mutationCandidates == [{"id": "a"}, {"id": "b"}]
    assert result.nodes[3]["properties"] == {
        "bytes": 5, "lineCount": 1, "sha256": "digest", "fanIn": 0, "fanOut": 1,
        "transitiveChangeImpact": 0, "instability": 1.0,
    }


def test_projection_aggregates_ancestors_counts_and_sorted_relationships_without_mutation() -> None:
    nodes = [graph_node("m", "module"), graph_node("b", "file", "m"), graph_node("a", "file", "m"),
             graph_node("class", "type", "a"), graph_node("fn", "callable", "class"),
             graph_node("fn2", "callable", "class"), graph_node("external", "external")]
    edges = [edge("fn", "b", "CALLS", confidence="INFERRED"), edge("a", "b", typeOnly=True),
             edge("fn", "fn2", "CALLS"), edge("b", "a", "REFERENCES"),
             edge("a", "b", "CONTAINS"), edge("fn", "external"), edge("missing", "a")]
    before = deepcopy((nodes, edges))

    result = artifact.build_dependency_views(nodes, edges)

    assert result == {
        "module": {"nodes": ["m"], "edges": []},
        "file": {"nodes": ["b", "a"], "edges": [
            {"sourceStableKey": "a", "targetStableKey": "b", "type": "DEPENDS_ON", "level": "file", "count": 2,
             "relationshipCounts": {"CALLS": 1, "IMPORTS": 1}, "confidenceCounts": {"EXTRACTED": 1, "INFERRED": 1}},
            {"sourceStableKey": "b", "targetStableKey": "a", "type": "DEPENDS_ON", "level": "file", "count": 1,
             "relationshipCounts": {"REFERENCES": 1}, "confidenceCounts": {"EXTRACTED": 1}},
        ]},
        "type": {"nodes": ["class"], "edges": []},
        "callable": {"nodes": ["fn", "fn2"], "edges": [
            {"sourceStableKey": "fn", "targetStableKey": "fn2", "type": "DEPENDS_ON", "level": "callable", "count": 1,
             "relationshipCounts": {"CALLS": 1}, "confidenceCounts": {"EXTRACTED": 1}},
        ]},
    }
    assert (nodes, edges) == before
    assert artifact.build_dependency_views(nodes, list(reversed(edges))) == result


def test_repository_languages_are_unique_and_sorted(extraction) -> None:
    languages = ["typescript", "rust", "ruby", "python", "php", "kotlin", "java", "javascript", "go", "c", "rust"]
    files = [parsed_file(f"source-{index}") for index in range(len(languages))]
    for file, language in zip(files, languages):
        file.source.language = language

    result = artifact.build_artifact(Path("/repo"), ParsedRepository(files), ResolvedGraph([], []))

    assert result.repository.get("languages") == [
        "c", "go", "java", "javascript", "kotlin", "php", "python", "ruby", "rust", "typescript",
    ]


@pytest.mark.parametrize("level", ["module", "file", "type", "callable"])
def test_projection_keeps_cross_ancestor_relationships_at_each_level(level: str) -> None:
    nodes = [graph_node("right", level), graph_node("left", level),
             graph_node("child", "symbol", "left")]

    result = artifact.build_dependency_views(nodes, [edge("child", "right")])

    assert result[level] == {"nodes": ["right", "left"], "edges": [{
        "sourceStableKey": "left", "targetStableKey": "right", "type": "DEPENDS_ON", "level": level,
        "count": 1, "relationshipCounts": {"IMPORTS": 1}, "confidenceCounts": {"EXTRACTED": 1},
    }]}


@pytest.mark.parametrize(("change", "message"), [
    ("duplicate", "duplicate stable node keys"), ("parent", "missing parent: absent"),
    ("source", "missing source: absent"), ("target", "missing target: absent"),
])
def test_reference_validation_catches_in_place_container_edits(empty_artifact, change, message) -> None:
    if change == "duplicate":
        empty_artifact.nodes.append(deepcopy(empty_artifact.nodes[0]))
    elif change == "parent":
        empty_artifact.nodes[1]["parentStableKey"] = "absent"
    else:
        empty_artifact.edges[0][change + "StableKey"] = "absent"

    with pytest.raises(ValueError, match=message):
        empty_artifact.validate_references()


@pytest.mark.parametrize("metric", ["fanIn", "fanOut", "transitiveChangeImpact"])
@pytest.mark.parametrize("value", [-1, True, 1.0, None])
def test_dependency_counts_require_exact_nonnegative_integers(empty_artifact, metric, value) -> None:
    empty_artifact.nodes[0]["properties"][metric] = value

    with pytest.raises(ValueError, match=f"{metric} must be a nonnegative integer"):
        empty_artifact.validate_references()


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), 0, True])
def test_instability_requires_finite_float_in_closed_unit_interval(empty_artifact, value) -> None:
    empty_artifact.nodes[0]["properties"]["instability"] = value

    with pytest.raises(ValueError, match="instability must be None or a finite float between 0 and 1"):
        empty_artifact.validate_references()


@pytest.mark.parametrize("value", [None, 0.0, 1.0])
def test_valid_dependency_boundaries_return_same_artifact(empty_artifact, value) -> None:
    empty_artifact.nodes[0]["properties"].update(fanIn=0, fanOut=2, transitiveChangeImpact=1, instability=value)

    assert empty_artifact.validate_references() is empty_artifact
    assert artifact.validate_artifact(empty_artifact) is None


@pytest.mark.parametrize("change", ["negative_stat", "extra_node_field", "invalid_line"])
def test_snapshot_validation_rechecks_schema_after_in_place_edits(empty_artifact, change) -> None:
    if change == "negative_stat":
        empty_artifact.stats["files"] = -1
    elif change == "extra_node_field":
        empty_artifact.nodes[0]["unexpected"] = 1
    else:
        empty_artifact.edges[0]["line"] = 0

    with pytest.raises(ValidationError):
        artifact.validate_artifact(empty_artifact)
