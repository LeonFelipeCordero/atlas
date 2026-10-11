"""Independent projection, reachability, compatibility and indexing checks."""

from tests.source_snapshot_fixture import case_bytes, case_text

from dataclasses import asdict
from pathlib import Path
from random import Random

import pytest
from pydantic import ValidationError

from atlas.metrics.artifact import (
    GraphArtifact, build_artifact, build_dependency_views, validate_artifact,
)
from atlas.metrics.dependency_metrics import METRIC_NAMES, dependency_metrics
from atlas.domain.models import (
    GraphNode,
    GraphView,
    ParsedFile,
    ParsedRepository,
    SourceFile,
    Symbol,
    file_key,
)
from atlas.metrics.resolver import Connection, ExternalNode, ResolvedGraph
from atlas.indexer import analyze_repository


def view(keys: list[str], pairs: list[tuple[str, str]]) -> GraphView:
    return {
        "nodes": keys,
        "edges": [
            {
                "sourceStableKey": source,
                "targetStableKey": target,
                "type": "DEPENDS_ON",
                "level": "file",
                "count": 3,
                "relationshipCounts": {"CALLS": 2, "REFERENCES": 1},
                "confidenceCounts": {"EXTRACTED": 3},
            }
            for source, target in pairs
        ],
    }


def counts(fan_in: int, fan_out: int, impact: int) -> dict[str, int]:
    return dict(zip(METRIC_NAMES, (fan_in, fan_out, impact)))


def expected_metrics(fan_in: int, fan_out: int, impact: int) -> dict[str, int | float | None]:
    return {
        **counts(fan_in, fan_out, impact),
        "instability": fan_out / (fan_in + fan_out) if fan_in + fan_out else None,
    }


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [
        ([("a", "b"), ("b", "c")], [(0, 1, 0), (1, 1, 1), (1, 0, 2)]),
        (
            [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
            [(0, 2, 0), (1, 1, 1), (1, 1, 1), (2, 0, 3)],
        ),
        (
            [("a", "b"), ("b", "c"), ("c", "b"), ("c", "d")],
            [(0, 1, 0), (2, 1, 2), (1, 2, 2), (1, 0, 3)],
        ),
        (
            [("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "c")],
            [(1, 1, 1), (1, 2, 1), (2, 1, 3), (1, 1, 3)],
        ),
    ],
)
def test_chain_diamond_and_cycles(pairs, expected) -> None:
    keys = list("abcd")[: len(expected)]
    actual = dependency_metrics(view([*keys, "isolated"], pairs))
    assert actual == {
        **{key: expected_metrics(*values) for key, values in zip(keys, expected)},
        "isolated": expected_metrics(0, 0, 0),
    }


def test_duplicate_self_and_outside_view_edges_do_not_count() -> None:
    graph = view(
        list("ab"),
        [
            ("a", "b"),
            ("a", "b"),
            ("a", "a"),
            ("b", "b"),
            ("a", "external"),
            ("external", "b"),
        ],
    )
    assert dependency_metrics(graph) == {
        "a": expected_metrics(0, 1, 0), "b": expected_metrics(1, 0, 1),
    }
    assert dependency_metrics(view([], [])) == {}


def test_instability_uses_distinct_incoming_and_outgoing_peers() -> None:
    peers = list("abcd")
    pairs = [(peer, "stable") for peer in peers] + [("stable", "unstable")]
    pairs += [("unstable", peer) for peer in peers]
    actual = dependency_metrics(view([*peers, "stable", "unstable", "isolated"], pairs))
    assert actual["stable"] == {**counts(4, 1, 5), "instability": 0.2}
    assert actual["unstable"] == {**counts(1, 4, 5), "instability": 0.8}
    assert actual["isolated"] == {**counts(0, 0, 0), "instability": None}
    assert all(actual[peer] == expected_metrics(1, 1, 5) for peer in peers)


def reverse_reachable(key: str, pairs: list[tuple[str, str]]) -> int:
    reverse: dict[str, set[str]] = {}
    for source, target in pairs:
        reverse.setdefault(target, set()).add(source)
    visited = {key}
    pending = [key]
    while pending:
        peers = reverse.get(pending.pop(), set()) - visited
        visited.update(peers)
        pending.extend(peers)
    return len(visited) - 1


@pytest.mark.parametrize("seed", range(20))
def test_bitsets_match_independent_traversal_on_mixed_graphs(seed: int) -> None:
    random = Random(seed)
    keys = [str(index) for index in range(40)]
    pairs = [(random.choice(keys), random.choice(keys)) for _ in range(65)]
    actual = dependency_metrics(view(keys, pairs))
    assert {
        key: metrics["transitiveChangeImpact"] for key, metrics in actual.items()
    } == {key: reverse_reachable(key, pairs) for key in keys}


def test_deep_graph_is_iterative_and_exact() -> None:
    keys = [str(index) for index in range(10_000)]
    actual = dependency_metrics(view(keys, list(zip(keys, keys[1:]))))
    assert actual == {
        key: expected_metrics(int(index > 0), int(index < len(keys) - 1), index)
        for index, key in enumerate(keys)
    }


def test_large_cycle_is_iterative_and_excludes_selected_node() -> None:
    keys = [str(index) for index in range(3_000)]
    actual = dependency_metrics(view(keys, list(zip(keys, [*keys[1:], keys[0]]))))
    assert all(metrics == expected_metrics(1, 1, len(keys) - 1) for metrics in actual.values())


def declaration(name: str, kind: str, owner: Symbol | SourceFile) -> Symbol:
    path = owner.file_path if isinstance(owner, Symbol) else owner.path
    parent = owner.key if isinstance(owner, Symbol) else file_key(path)
    return Symbol(
        name, path, "python", name, name, kind, parent, 0, 1, 1, 1, 1, 2, None, None, []
    )


def projected_artifact(root: Path) -> GraphArtifact:
    files = []
    for name in "abcdz":
        path = f"{name}/{name}.py"
        source = SourceFile(path, root / path, "python", case_bytes("imports", "dependency-metrics-projected-artifact-1", path))
        type_symbol = declaration(f"type:{name}", "class", source)
        files.append(
            ParsedFile(
                source,
                "hash",
                None,
                [
                    type_symbol,
                    declaration(name, "method", type_symbol),
                ],
            )
        )
    edges = [
        Connection("a", "b", "CALLS", "EXTRACTED", "a/a.py", 1, None),
        Connection("a", "b", "REFERENCES", "EXTRACTED", "a/a.py", 2, None),
        Connection("a", "c", "IMPORTS", "EXTRACTED", "a/a.py", 3, None, True),
        Connection("b", "d", "INHERITS", "EXTRACTED", "b/b.py", 1, None),
        Connection("c", "d", "REFERENCES", "EXTRACTED", "c/c.py", 1, None),
        Connection("a", "a", "CALLS", "EXTRACTED", "a/a.py", 4, None),
        Connection("a", "type:a", "REFERENCES", "EXTRACTED", "a/a.py", 5, None),
        Connection("a", "external", "IMPORTS", "EXTRACTED", "a/a.py", 6, None),
        Connection("external", "b", "CALLS", "EXTRACTED", "a/a.py", 7, None),
        Connection("a", "d", "CONTAINS", "EXTRACTED", "a/a.py", 8, None),
    ]
    return build_artifact(
        root,
        ParsedRepository(files),
        ResolvedGraph(
            edges, [ExternalNode("external", "python", "callable", "missing")]
        ),
    )


def metric_values(node: GraphNode) -> dict[str, int]:
    return {metric: node["properties"][metric] for metric in METRIC_NAMES}


def assert_projected_peer_metrics(
    nodes: dict[str, GraphNode], name: str, values: tuple[int, int, int]
) -> None:
    keys = [name, f"type:{name}", f"file:{name}/{name}.py", f"module:{name}"]
    expected = expected_metrics(*values)
    assert all(metric_values(nodes[key]) == counts(*values) for key in keys)
    assert all(nodes[key]["properties"]["instability"] == expected["instability"] for key in keys)


def test_all_levels_use_aggregated_internal_dependencies(tmp_path: Path) -> None:
    artifact = projected_artifact(tmp_path)
    nodes = {node["stableKey"]: node for node in artifact.nodes}
    expected = {
        "a": (0, 2, 0),
        "b": (1, 1, 1),
        "c": (1, 1, 1),
        "d": (2, 0, 3),
        "z": (0, 0, 0),
    }
    for name, values in expected.items():
        assert_projected_peer_metrics(nodes, name, values)
    assert nodes["module:."]["properties"] == expected_metrics(0, 0, 0)
    assert nodes["external"]["properties"] == {}
    assert not set(METRIC_NAMES).intersection(nodes["repository"]["properties"])
    # Type-only is included in metrics but not runtime import cycle detection.
    assert artifact.circularDependencies == {"version": 1, "groups": []}
    assert len(artifact.views["callable"]["edges"]) == 4
    assert artifact.views["callable"]["edges"][0]["count"] == 2
    snapshot = asdict(artifact)
    assert build_dependency_views(snapshot["nodes"], snapshot["edges"]) == artifact.views


def test_indexer_populates_metrics_and_excludes_unresolved_targets(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text(
        case_text("imports", "dependency-metrics-indexer-populates-metrics-and-excludes-unresolved-targets", 'a.py')
    )
    (tmp_path / "b.py").write_text(
        case_text("imports", "dependency-metrics-indexer-populates-metrics-and-excludes-unresolved-targets", 'b.py')
    )
    (tmp_path / "c.py").write_text(case_text("imports", "dependency-metrics-indexer-populates-metrics-and-excludes-unresolved-targets", 'c.py'))
    (tmp_path / "z.py").write_text(case_text("imports", "dependency-metrics-indexer-populates-metrics-and-excludes-unresolved-targets", 'z.py'))
    artifact = analyze_repository(tmp_path)
    nodes = {node["name"]: node for node in artifact.nodes}
    for name, values in {
        "a.py": (0, 1, 0),
        "b.py": (1, 1, 1),
        "c.py": (1, 0, 2),
        "entry": (0, 1, 0),
        "middle": (1, 1, 1),
        "leaf": (1, 0, 2),
        "isolated": (0, 0, 0),
    }.items():
        assert metric_values(nodes[name]) == counts(*values)
        assert nodes[name]["properties"]["instability"] == expected_metrics(*values)["instability"]
    assert nodes["missing"]["level"] == "external"
    assert nodes["missing"]["properties"] == {}


def test_type_only_imports_contribute_compile_time_impact(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_text(
        case_text("imports", "dependency-metrics-type-only-imports-contribute-compile-time-impact", 'a.ts')
    )
    (tmp_path / "b.ts").write_text(
        case_text("imports", "dependency-metrics-type-only-imports-contribute-compile-time-impact", 'b.ts')
    )
    artifact = analyze_repository(tmp_path)
    files = [node for node in artifact.nodes if node["level"] == "file"]
    assert len(files) == 2
    assert all(metric_values(node) == counts(1, 1, 1) for node in files)
    assert all(node["properties"]["instability"] == 0.5 for node in files)
    assert any(edge.get("typeOnly") for edge in artifact.edges)
    assert artifact.circularDependencies == {"version": 1, "groups": []}


def strip_metrics(node: GraphNode) -> None:
    for name in (*METRIC_NAMES, "instability"):
        node["properties"].pop(name, None)


def test_legacy_metrics_are_optional_and_round_trip(tmp_path: Path) -> None:
    data = asdict(projected_artifact(tmp_path))
    for node in data["nodes"]:
        strip_metrics(node)
    assert asdict(GraphArtifact(**data)) == data


@pytest.mark.parametrize("name", METRIC_NAMES)
@pytest.mark.parametrize("value", [-1, 1.5, True, "1", None])
def test_metric_properties_require_nonnegative_integer_counts(
    tmp_path: Path, name: str, value: object
) -> None:
    data = asdict(projected_artifact(tmp_path))
    data["nodes"][1]["properties"][name] = value
    with pytest.raises(ValidationError, match=f"{name} must be a nonnegative integer"):
        GraphArtifact(**data)


@pytest.mark.parametrize("value", [None, 0.0, 0.2, 0.8, 1.0])
def test_instability_accepts_none_and_finite_unit_interval_floats(
    tmp_path: Path, value: float | None
) -> None:
    data = asdict(projected_artifact(tmp_path))
    data["nodes"][1]["properties"]["instability"] = value
    artifact = GraphArtifact(**data)
    assert artifact.nodes[1]["properties"]["instability"] == value
    validate_artifact(artifact)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("inf"), float("-inf"), float("nan"), 0, 1, True, "0.2"])
def test_instability_requires_none_or_a_finite_unit_interval_float(
    tmp_path: Path, value: object
) -> None:
    artifact = projected_artifact(tmp_path)
    artifact.nodes[1]["properties"]["instability"] = value
    with pytest.raises(ValidationError, match="instability must be None or a finite float between 0 and 1"):
        validate_artifact(artifact)
    with pytest.raises(ValidationError, match="instability must be None or a finite float between 0 and 1"):
        GraphArtifact(**asdict(artifact))
