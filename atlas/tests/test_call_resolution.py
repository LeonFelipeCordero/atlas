import tempfile
import unittest
from pathlib import Path

from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import _extract_calls
from atlas.indexer import analyze_repository


# The same collision in different grammars, without language-specific resolution.
SAMPLES = {
    "kt": ("fun from(x: Int) = x", "fun run() { context.select(X).from(X); from(X) }"),
    "ts": (
        "function from(x) { return x }",
        "function run() { context.select(X).from(X); from(X) }",
    ),
    "py": (
        "def convert(x): return x",
        "def run():\n context.select(X).convert(X)\n convert(X)",
    ),
    "java": (
        "class Factory { static int from(int x) { return x; } }",
        "class App { void run() { context.select(X).from(X); from(X); } }",
    ),
    "go": (
        "package main\nfunc Convert(x int) int { return x }",
        "package main\nfunc run(){ context.Select(X).Convert(X); Convert(X) }",
    ),
    "rs": (
        "fn convert(x: i32) -> i32 { x }",
        "fn run(){ context.select(x).convert(x); convert(x); }",
    ),
    "cs": (
        "class Factory { static int Convert(int x) { return x; } }",
        "class App { void Run(){ context.Select(x).Convert(x); Convert(x); } }",
    ),
    "rb": (
        "def convert(x)\n x\nend",
        "def run()\n context.select(x).convert(x)\n convert(x)\nend",
    ),
}


class CallResolutionTest(unittest.TestCase):
    def test_member_collisions_never_use_local_or_global_name_fallback(self) -> None:
        for extension, (declaration, usage) in SAMPLES.items():
            self.check_collision_locations(extension, declaration, usage)

    def check_collision_locations(self, extension, declaration, usage) -> None:
        for local in (False, True):
            with self.subTest(extension=extension, local=local):
                self.check_collision(extension, declaration, usage, local)

    def check_collision(
        self, extension: str, declaration: str, usage: str, local: bool
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Go requires just one package declaration in a combined source file.
            combined = declaration + "\n" + usage.replace("package main\n", "")
            (root / f"app.{extension}").write_text(combined if local else usage)
            if not local:
                (root / f"factory.{extension}").write_text(declaration)
            artifact = analyze_repository(root)
            self.assert_collision_calls(artifact)

    def assert_collision_calls(self, artifact) -> None:
        calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
        member_calls = [edge for edge in calls if "." in str(edge["evidence"])]
        self.assertTrue(member_calls)
        self.assertTrue(
            all(
                str(edge["targetStableKey"]).startswith("external:")
                for edge in member_calls
            )
        )
        self.assert_bare_collision_calls(calls)

    def assert_bare_collision_calls(self, calls) -> None:
        bare_calls = [edge for edge in calls if "." not in str(edge["evidence"])]
        self.assertTrue(
            any(
                str(edge["targetStableKey"]).startswith("symbol:")
                for edge in bare_calls
            )
        )

    def test_computed_and_qualified_targets_are_not_bare(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.ts").write_text(
                "obj.convert(x); handlers[key](argument); factory(argument)(x); helper(x)"
            )
            source = next(iter(discover_files(root)))
            calls = _extract_calls(source)
            self.assertTrue(calls)
            for call in calls:
                self.assertEqual(call.bare_target, call.name in {"factory", "helper"})
            computed = next(
                call for call in calls if call.evidence == "handlers[key](argument)"
            )
            self.assertEqual(computed.name, "handlers[key]")

    def test_ambiguous_bare_call_stays_external(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.ts").write_text("export function helper() {}")
            (root / "b.ts").write_text("export function helper() {}")
            (root / "app.ts").write_text("helper()")
            artifact = analyze_repository(root)
            call = next(edge for edge in artifact.edges if edge["type"] == "CALLS")
            self.assertTrue(str(call["targetStableKey"]).startswith("external:"))

    def test_jooq_from_does_not_resolve_to_response_factory(self) -> None:
        declaration = "class BulkOperationResponse { companion object { fun from(result: BulkOperationResult) = BulkOperationResponse() } }"
        usage = "class ChannelRepository { fun findById() = context.select(CHANNELS.asterisk()).from(CHANNELS) }"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "QueueApi.kt").write_text(declaration)
            (root / "ChannelRepository.kt").write_text(usage)
            artifact = analyze_repository(root)
            calls = [
                edge
                for edge in artifact.edges
                if edge["type"] == "CALLS" and edge["path"] == "ChannelRepository.kt"
            ]
            self.assertTrue(calls)
            self.assertTrue(
                all(
                    str(edge["targetStableKey"]).startswith("external:")
                    for edge in calls
                )
            )
