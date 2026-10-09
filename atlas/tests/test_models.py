import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from atlas.domain.artifact import GraphArtifact, validate_artifact
from atlas.discovery import SourceFile
from atlas.domain.models import ParsedFile
from atlas.indexer import analyze_repository
from atlas.domain.resolver import Connection


class ModelsTest(unittest.TestCase):
    def artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("def hello():\n    return 1\nhello()\n")
            return analyze_repository(root)

    def test_language_graphs_round_trip_without_field_changes(self):
        from tests.coffee_fixture import LANGUAGES, coffee_graph

        for language in LANGUAGES:
            with self.subTest(language=language):
                expected = asdict(coffee_graph(language))
                artifact = GraphArtifact(**expected)
                self.assertEqual(asdict(artifact), expected)
                self.assertEqual(json.loads(json.dumps(asdict(artifact))), expected)

    def test_positional_constructors_and_default_lists(self):
        source = SourceFile("example.py", Path("example.py"), "python", b"")
        first = ParsedFile(source, "hash", None)
        second = ParsedFile(source, "hash", None)
        self.assertIsNot(first.calls, second.calls)
        self.assertIsNot(first.symbols, second.symbols)
        legacy = GraphArtifact(2, {}, {}, [], [], {}, [])
        self.assertIsNone(asdict(legacy)["circularDependencies"])

    def test_strict_constructor_and_assignment_validation(self):
        with self.assertRaises(ValidationError):
            SourceFile("example.py", Path("example.py"), "python", cast(Any, "not bytes"))
        with self.assertRaises(ValidationError):
            Connection("a", "b", cast(Any, "UNKNOWN"), "INFERRED", "example.py", 1, None)
        source = SourceFile("example.py", Path("example.py"), "python", b"")
        with self.assertRaises(ValidationError):
            setattr(source, "language", 123)

    def test_invalid_artifact_fields_are_rejected(self):
        original = asdict(self.artifact())
        cases = [
            ("schemaVersion", 3),
            ("stats", {"files": "1"}),
            ("stats", {"files": -1}),
        ]
        for field, value in cases:
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(ValidationError),
            ):
                data: dict[str, Any] = {**original, field: value}
                GraphArtifact(**data)
        for field, value in [("level", "unknown"), ("depth", -1), ("unexpected", True)]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                data = {**original, "nodes": [{**original["nodes"][0], field: value}]}
                GraphArtifact(**data)

    def test_reference_validation_runs_at_construction(self):
        original = asdict(self.artifact())
        invalid_nodes = [*original["nodes"], original["nodes"][0]]
        with self.assertRaisesRegex(ValidationError, "duplicate stable node keys"):
            data: dict[str, Any] = {**original, "nodes": invalid_nodes}
            GraphArtifact(**data)
        for field, message in [
            ("parentStableKey", "missing parent"),
            ("sourceStableKey", "missing source"),
            ("targetStableKey", "missing target"),
        ]:
            data = asdict(self.artifact())
            collection = "nodes" if field == "parentStableKey" else "edges"
            data[collection][0][field] = "missing"
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValidationError, message),
            ):
                GraphArtifact(**data)

    def test_mutation_is_revalidated_in_memory(self):
        artifact = self.artifact()
        artifact.edges[0]["line"] = "1"  # pyright: ignore[reportGeneralTypeIssues]
        with self.assertRaises(ValidationError):
            validate_artifact(artifact)
