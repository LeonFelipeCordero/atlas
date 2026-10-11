
from tests.source_snapshot_fixture import case_text
from tests.import_snapshot_support import write_import_case
import tempfile
import unittest
from itertools import product
from pathlib import Path

from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import _extract_calls
from atlas.indexer import analyze_repository


class CallResolutionTest(unittest.TestCase):
    def test_member_collisions_never_use_local_or_global_name_fallback(self) -> None:
        for extension, location in product(("kt", "ts", "py", "java", "go", "rs", "cs", "rb"), ("local", "global")):
            with self.subTest(extension=extension, location=location), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_import_case(root, f"collision-{extension}-{location}")
                self.assert_collision_calls(analyze_repository(root))

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
                case_text("imports", "call-resolution-computed-and-qualified-targets-are-not-bare-1", 'app.ts')
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
            (root / "a.ts").write_text(case_text("imports", "call-resolution-ambiguous-bare-call-stays-external", 'a.ts'))
            (root / "b.ts").write_text(case_text("imports", "call-resolution-ambiguous-bare-call-stays-external", 'b.ts'))
            (root / "app.ts").write_text(case_text("imports", "call-resolution-ambiguous-bare-call-stays-external", 'app.ts'))
            artifact = analyze_repository(root)
            call = next(edge for edge in artifact.edges if edge["type"] == "CALLS")
            self.assertTrue(str(call["targetStableKey"]).startswith("external:"))

    def test_jooq_from_does_not_resolve_to_response_factory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_import_case(root, "jooq-response-factory")
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
