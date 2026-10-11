"""Independent Rust module-graph invariants over complete fixture projects."""

from tests.resolution_snapshot_support import fixture_sources, fixture_text
import unittest
from pathlib import Path
from atlas.parsing.discovery import SourceFile
from atlas.domain.models import ParsedRepository
from atlas.parsing.parser import parse_files
from atlas.metrics.adapters.rust import RustModules
from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.resolution_syntax import Syntax
from atlas.metrics.resolver import resolve_connections


def repository(sources: dict[str, str]) -> ParsedRepository:
    return parse_files(
        [
            SourceFile(path, Path("/module-tests") / path, "rust", source.encode())
            for path, source in sources.items()
        ]
    )


def modules(repo: ParsedRepository) -> RustModules:
    return RustModules(
        repo,
        {f.source.path: Syntax(f, get_resolution_adapter("rust")) for f in repo.files},
    )


class RustModulesTest(unittest.TestCase):
    def assert_call(self, repo: ParsedRepository, evidence: str, path: str | None):
        edges = [
            e
            for e in resolve_connections(repo).connections
            if e.type == "CALLS" and e.evidence == evidence
        ]
        self.assertTrue(edges, evidence)
        if path is None:
            self.assertTrue(
                all((e.target_key.startswith("external:") for e in edges)), edges
            )
            return
        self.assert_work_target(repo, path, edges)

    def assert_work_target(self, repo, path, edges):
        target = next(
            (s for s in repo.symbols if s.file_path == path and s.name == "work")
        )
        self.assertEqual({e.target_key for e in edges}, {target.key})

    def test_external_module_owner_is_not_a_second_crate_root(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_external_module_owner_is_not_a_second_crate_root:53-15"
            )
        )
        self.assert_call(repo, "crate::inner::work()", None)
        self.assert_call(repo, "crate::outer::inner::work()", "outer/inner.rs")
        self.assertEqual(modules(repo).rust_files("crate::inner"), [])

    def test_inline_ancestry_selects_nested_file_not_root_level_decoy(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_inline_ancestry_selects_nested_file_not_root_level_decoy:65-15"
            )
        )
        self.assert_call(repo, "crate::outer::inner::work()", "outer/inner.rs")
        self.assert_call(repo, "crate::inner::work()", None)

    def test_deep_inline_modules_and_mod_rs_layout(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_deep_inline_modules_and_mod_rs_layout:76-15"
            )
        )
        self.assert_call(
            repo, "crate::outer::middle::inner::work()", "src/outer/middle/inner/mod.rs"
        )

    def test_inline_modules_inside_external_file_keep_file_stem_directory(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_inline_modules_inside_external_file_keep_file_stem_directory:87-15"
            )
        )
        self.assert_call(
            repo, "crate::outer::middle::inner::work()", "outer/middle/inner.rs"
        )

    def test_path_attribute_is_found_above_other_attributes_and_comments(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_path_attribute_is_found_above_other_attributes_and_comments:100-15"
            )
        )
        self.assert_call(repo, "worker::work()", "odd/worker.rs")

    def test_external_path_attribute_is_relative_to_containing_file(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_external_path_attribute_is_relative_to_containing_file:110-15"
            )
        )
        self.assert_call(repo, "crate::outer::inner::work()", "odd/worker.rs")
        self.assert_call(repo, "crate::inner::work()", None)

    def test_path_attributes_inside_inline_modules_use_inline_directory(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_path_attributes_inside_inline_modules_use_inline_directory:121-15"
            )
        )
        self.assert_call(repo, "crate::outer::inner::work()", "odd/worker.rs")

    def test_inline_path_attribute_sets_child_directory(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_inline_path_attribute_sets_child_directory:131-15"
            )
        )
        self.assert_call(repo, "crate::outer::inner::work()", "alternate/inner.rs")

    def test_standard_roots_exclude_unattached_module_owners(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_standard_roots_exclude_unattached_module_owners:141-15"
            )
        )
        self.assert_call(repo, "crate::inner::work()", None)

    def test_nonstandard_coffee_root_with_explicit_paths(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_nonstandard_coffee_root_with_explicit_paths:151-15"
            )
        )
        self.assert_call(repo, "recipe::work()", "brewing/recipe.rs")
        self.assert_call(repo, "crate::report::work()", "reporting/report.rs")

    def test_nonstandard_root_discovery_excludes_referenced_module_owners(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_nonstandard_root_discovery_excludes_referenced_module_owners:162-15"
            )
        )
        self.assert_call(repo, "crate::inner::work()", None)
        self.assert_call(repo, "crate::outer::inner::work()", "outer/inner.rs")

    def test_multiple_standard_and_nonstandard_roots_remain_ambiguous(self):
        for entry in ("main.rs", "entry.rs"):
            with self.subTest(entry=entry):
                repo = repository(
                    fixture_sources(
                        "resolution_modules:test_multiple_standard_and_nonstandard_roots_remain_ambiguous:175-23",
                        entry=entry,
                    )
                )
                self.assert_call(repo, "crate::tools::work()", None)

    def test_lib_and_main_roots_are_ambiguous_even_when_they_share_a_file(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_lib_and_main_roots_are_ambiguous_even_when_they_share_a_file:186-15"
            )
        )
        self.assert_call(repo, "crate::tools::work()", None)

    def test_relative_module_aliases_require_inline_lexical_position(self):
        source = fixture_text(
            "resolution_modules:test_relative_module_aliases_require_inline_lexical_position:197-15",
            "main.rs",
        )
        repo = repository(
            fixture_sources(
                "resolution_modules:test_relative_module_aliases_require_inline_lexical_position:197-15"
            )
        )
        index, file = (modules(repo), repo.files[0])
        position = source.index("mod inner;", source.index("mod outer"))
        self.assertEqual(
            [f.source.path for f in index.rust_import(file, "inner", position)],
            ["outer/inner.rs"],
        )
        self.assertEqual(
            [f.source.path for f in index.rust_import(file, "self::inner", position)],
            ["outer/inner.rs"],
        )
        self.assertEqual(
            [f.source.path for f in index.rust_import(file, "super::inner", position)],
            ["inner.rs"],
        )
        self.assertEqual(
            [f.source.path for f in index.rust_import(file, "inner", 0)], ["inner.rs"]
        )
        self.assertEqual(index.rust_import(file, "super::inner", 0), [])

    def test_inline_namespaces_expose_only_direct_symbols_not_the_whole_file(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_inline_namespaces_expose_only_direct_symbols_not_the_whole_file:224-15"
            )
        )
        index, file = (modules(repo), repo.files[0])
        self.assertEqual(index.rust_import(file, "crate::outer"), [])
        actual = index.rust_symbols(file, "crate::outer")
        expected = [
            s
            for s in file.symbols
            if s.qualified_name.endswith("::outer.work") or s.name == "nested"
        ]
        self.assertEqual({s.key for s in actual}, {s.key for s in expected})
        self.assertEqual(len([s for s in actual if s.name == "work"]), 1)

    def test_recursive_path_module_graph_terminates_without_false_root(self):
        repo = repository(
            fixture_sources(
                "resolution_modules:test_recursive_path_module_graph_terminates_without_false_root:241-15"
            )
        )
        self.assert_call(repo, "crate::inner::work()", None)
        self.assertEqual(modules(repo).rust_files("crate::outer::inner"), [])


if __name__ == "__main__":
    unittest.main()
