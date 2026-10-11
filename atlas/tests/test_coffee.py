"""Full Python-indexer snapshots plus source-reviewed semantic coverage checks."""

import unittest
from collections import Counter

from atlas.metrics.artifact import validate_artifact
from tests.coffee_fixture import (
    FIXTURE_ROOT,
    LANGUAGES,
    SNAPSHOT_ROOT,
    coffee_graph,
    coffee_snapshot,
)
from tests.coffee_integrity import assert_coffee_integrity
from tests.coffee_scenarios import CALL_SITES, CORE_LANGUAGES, DECLARATIONS, declaration_gaps
from tests.coffee_snapshot_assertions import (
    assert_call_sites,
    assert_layout,
    assert_project_calls,
    assert_recursion_scenarios,
    assert_render_paths,
    assert_score,
    assert_snapshot,
)


class CoffeeSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = {language: coffee_graph(language) for language in LANGUAGES}
        cls.graphs = {
            language: coffee_snapshot(artifact)
            for language, artifact in cls.artifacts.items()
        }

    def test_every_supported_sample_has_a_python_baseline(self) -> None:
        self.assertEqual(set(DECLARATIONS), set(LANGUAGES))
        self.assertTrue(
            all((FIXTURE_ROOT / language).is_dir() for language in LANGUAGES)
        )
        self.assertTrue(
            all(
                (SNAPSHOT_ROOT / f"{language}-coffee.json").is_file()
                for language in LANGUAGES
            )
        )

    def test_all_supported_complete_graph_snapshots(self) -> None:
        for language in LANGUAGES:
            with self.subTest(language=language):
                assert_snapshot(self, language, self.artifacts[language])

    def test_real_layout_hashes_and_coordinates(self) -> None:
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                assert_layout(self, language, graph)

    def test_hierarchy_views_cycles_and_stats_have_no_dangling_references(self) -> None:
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                validate_artifact(self.artifacts[language])
                assert_coffee_integrity(self, graph)

    def test_complete_source_inventory_without_missing_or_spurious_declarations(
        self,
    ) -> None:
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                missing, extra = declaration_gaps(graph)
                expected = [Counter()] * len(DECLARATIONS[language])
                self.assertEqual(missing, expected)
                self.assertEqual(extra, expected)

    def test_recursion_inheritance_callbacks_imports_and_file_cycles(self) -> None:
        for language in CORE_LANGUAGES:
            with self.subTest(language=language):
                assert_recursion_scenarios(self, language, self.graphs[language])

    def test_every_reviewed_call_site_is_grounded_in_sample_source(self) -> None:
        self.assertEqual(set(CALL_SITES), set(LANGUAGES))
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                assert_call_sites(self, language, graph)

    def test_empty_filter_preview_and_nonempty_render_paths(self) -> None:
        for language in CORE_LANGUAGES:
            with self.subTest(language=language):
                assert_render_paths(self, language, self.graphs[language])

    def test_nested_score_complexity(self) -> None:
        for language in CORE_LANGUAGES:
            with self.subTest(language=language):
                assert_score(self, language, self.graphs[language])

    def test_project_call_resolution_and_exact_known_limitations(self) -> None:
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                assert_project_calls(self, graph)

    def test_repeated_indexing_is_deterministic_except_timestamp(self) -> None:
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(
                    coffee_snapshot(coffee_graph(language)), self.graphs[language]
                )


if __name__ == "__main__":
    unittest.main()
