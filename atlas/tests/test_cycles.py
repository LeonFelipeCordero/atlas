import copy
import random
import tempfile
import unittest
from pathlib import Path

from dataclasses import asdict

from atlas.domain.artifact import GraphArtifact, validate_artifact
from atlas.domain.cycles import circular_dependencies
from atlas.indexer import analyze_repository


def file(key: str) -> dict[str, object]:
    return {"stableKey": key, "type": "file", "level": "file"}


def edge(source: str, target: str, kind: str = "IMPORTS") -> dict[str, object]:
    return {
        "sourceStableKey": source,
        "targetStableKey": target,
        "type": kind,
        "path": "original.py",
        "line": 7,
        "evidence": "import example",
        "confidence": "INFERRED",
    }


class CyclesTest(unittest.TestCase):
    def test_acyclic_and_empty(self) -> None:
        self.assertEqual(circular_dependencies([], []), {"version": 1, "groups": []})
        result = circular_dependencies([file("a"), file("b")], [edge("a", "b")])
        self.assertEqual(result["groups"], [])

    def test_sccs_witness_and_internal_edges(self) -> None:
        nodes = [file(key) for key in "abcde"]
        edges = [edge(a, b) for a, b in ("ab", "ba", "bc", "ca", "cd", "de", "ed")]
        groups = circular_dependencies(nodes, edges)["groups"]
        self.assertEqual(
            [group["nodeStableKeys"] for group in groups], [list("abc"), list("de")]
        )
        self.assertEqual([len(group["edges"]) for group in groups], [4, 2])
        for group in groups:
            self.assert_cycle_witness(group)

    def assert_cycle_witness(self, group) -> None:
        cycle = group["exampleCycle"]
        self.assertEqual(cycle[0], cycle[-1])
        pairs = {
            (item["sourceStableKey"], item["targetStableKey"])
            for item in group["edges"]
        }
        self.assertTrue(all(pair in pairs for pair in zip(cycle, cycle[1:])))

    def test_projection_preserves_evidence_without_mutation(self) -> None:
        nodes = [
            file("a"),
            file("b"),
            {"stableKey": "s", "type": "class", "parentStableKey": "a"},
            {"stableKey": "t", "type": "method", "parentStableKey": "s"},
        ]
        edges = [edge("t", "b"), edge("b", "s")]
        original = copy.deepcopy((nodes, edges))
        group = circular_dependencies(nodes, edges)["groups"][0]
        self.assertEqual(group["nodeStableKeys"], ["a", "b"])
        self.assertEqual(group["edges"], [edge("a", "b"), edge("b", "a")])
        self.assertEqual((nodes, edges), original)

    def test_only_genuine_file_self_import(self) -> None:
        nodes = [
            file("a"),
            {"stableKey": "s", "type": "function", "parentStableKey": "a"},
        ]
        edges = [edge("a", "s"), edge("s", "a"), edge("s", "s")]
        self.assertEqual(circular_dependencies(nodes, edges)["groups"], [])
        edges.append(edge("a", "a"))
        group = circular_dependencies(nodes, edges)["groups"][0]
        self.assertEqual(group["exampleCycle"], ["a", "a"])
        self.assertEqual(group["edges"], [edge("a", "a")])

    def test_external_missing_and_non_import_edges_ignored(self) -> None:
        nodes = [
            file("a"),
            file("b"),
            {"stableKey": "x", "type": "external", "parentStableKey": "a"},
            {"stableKey": "module", "type": "module"},
        ]
        edges = [
            edge("a", "b"),
            edge("a", "x"),
            edge("x", "a"),
            edge("a", "missing"),
            edge("module", "a"),
            edge("a", "module"),
        ]
        edges.extend(
            edge("b", "a", kind)
            for kind in ("CALLS", "CONTAINS", "INHERITS", "DEPENDS_ON")
        )
        self.assertEqual(circular_dependencies(nodes, edges)["groups"], [])

    def test_determinism_and_optional_metadata(self) -> None:
        nodes = [file(key) for key in "abcd"]
        edges = [edge(a, b) for a, b in ("ab", "ba", "cd", "dc")]
        edges.append(
            {"sourceStableKey": "a", "targetStableKey": "b", "type": "IMPORTS"}
        )
        expected = circular_dependencies(nodes, edges)
        rng = random.Random(42)
        for _ in range(10):
            rng.shuffle(nodes)
            rng.shuffle(edges)
            self.assertEqual(circular_dependencies(nodes, edges), expected)
        changed = copy.deepcopy(edges)
        changed[0]["line"] = 100
        self.assertEqual(
            [g["id"] for g in circular_dependencies(nodes, changed)["groups"]],
            [g["id"] for g in expected["groups"]],
        )

    def test_large_chain_and_cycle_are_iterative(self) -> None:
        keys = [f"file:{index:05d}" for index in range(5000)]
        nodes = [file(key) for key in keys]
        edges = [edge(a, b) for a, b in zip(keys, keys[1:])]
        self.assertEqual(circular_dependencies(nodes, edges)["groups"], [])
        edges.append(edge(keys[-1], keys[0]))
        groups = circular_dependencies(nodes, edges)["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["exampleCycle"], keys + [keys[0]])

    def test_indexing_and_legacy_constructor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("import b\n")
            (root / "b.py").write_text("import a\n")
            artifact = analyze_repository(root)
            saved = asdict(artifact)
            self.assertEqual(
                saved["circularDependencies"], artifact.circularDependencies
            )
            self.assertEqual(
                saved["circularDependencies"]["groups"][0]["nodeStableKeys"],
                ["file:a.py", "file:b.py"],
            )
            self.assertEqual(saved["schemaVersion"], 2)
            legacy = GraphArtifact(2, {}, {}, [], [], {}, [])
            self.assertIsNone(legacy.circularDependencies)
            validate_artifact(legacy)
            self.assertIsNone(asdict(legacy)["circularDependencies"])
