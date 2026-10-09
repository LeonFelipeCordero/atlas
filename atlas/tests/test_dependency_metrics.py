"""Independent projection, reachability, compatibility and indexing checks."""

from dataclasses import asdict
from pathlib import Path
from random import Random

import pytest
from pydantic import ValidationError

from atlas.metrics.artifact import GraphArtifact, build_artifact
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
        **{key: counts(*values) for key, values in zip(keys, expected)},
        "isolated": counts(0, 0, 0),
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
    assert dependency_metrics(graph) == {"a": counts(0, 1, 0), "b": counts(1, 0, 1)}
    assert dependency_metrics(view([], [])) == {}


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
        key: counts(int(index > 0), int(index < len(keys) - 1), index)
        for index, key in enumerate(keys)
    }


def test_large_cycle_is_iterative_and_excludes_selected_node() -> None:
    keys = [str(index) for index in range(3_000)]
    actual = dependency_metrics(view(keys, list(zip(keys, [*keys[1:], keys[0]]))))
    assert all(metrics == counts(1, 1, len(keys) - 1) for metrics in actual.values())


def declaration(name: str, kind: str, path: str, parent: str) -> Symbol:
    return Symbol(
        name, path, "python", name, name, kind, parent, 0, 1, 1, 1, 1, 2, None, None, []
    )


def projected_artifact(root: Path) -> GraphArtifact:
    files = []
    for name in "abcdz":
        path = f"{name}/{name}.py"
        files.append(
            ParsedFile(
                SourceFile(path, root / path, "python", b""),
                "hash",
                None,
                [
                    declaration(f"type:{name}", "class", path, file_key(path)),
                    declaration(name, "method", path, f"type:{name}"),
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
    assert all(metric_values(nodes[key]) == counts(*values) for key in keys)


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
    assert nodes["module:."]["properties"] == counts(0, 0, 0)
    assert nodes["external"]["properties"] == {}
    assert not set(METRIC_NAMES).intersection(nodes["repository"]["properties"])
    # Type-only is included in metrics but not runtime import cycle detection.
    assert artifact.circularDependencies == {"version": 1, "groups": []}
    assert len(artifact.views["callable"]["edges"]) == 4
    assert artifact.views["callable"]["edges"][0]["count"] == 2


def test_indexer_populates_metrics_and_excludes_unresolved_targets(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text(
        "from b import middle\nimport missing\ndef entry():\n    return middle()\n"
    )
    (tmp_path / "b.py").write_text(
        "from c import leaf\ndef middle():\n    return leaf()\n"
    )
    (tmp_path / "c.py").write_text("def leaf():\n    return 1\n")
    (tmp_path / "z.py").write_text("def isolated():\n    return 0\n")
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
    assert nodes["missing"]["level"] == "external"
    assert nodes["missing"]["properties"] == {}


def test_type_only_imports_contribute_compile_time_impact(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_text(
        'import type { B } from "./b";\nexport interface A { other: B; }\n'
    )
    (tmp_path / "b.ts").write_text(
        'import type { A } from "./a";\nexport interface B { other: A; }\n'
    )
    artifact = analyze_repository(tmp_path)
    files = [node for node in artifact.nodes if node["level"] == "file"]
    assert len(files) == 2
    assert all(metric_values(node) == counts(1, 1, 1) for node in files)
    assert any(edge.get("typeOnly") for edge in artifact.edges)
    assert artifact.circularDependencies == {"version": 1, "groups": []}


def strip_metrics(node: GraphNode) -> None:
    for name in METRIC_NAMES:
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
