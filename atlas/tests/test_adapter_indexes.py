"""Repository indexes are constructed only by the adapters present in a scan."""

import unittest

from atlas.metrics.adapters.rust import RustModules
from atlas.metrics.adapters import get_resolution_adapter
from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.resolution import Modules
from atlas.metrics.resolution_syntax import Syntax
from tests.test_semantic_resolution import repository


def indexes(repo):
    return Modules(
        repo,
        {
            file.source.path: Syntax(file, get_resolution_adapter(file.source.language))
            for file in repo.files
        },
    ).indexes


class AdapterIndexTest(unittest.TestCase):
    def test_unrelated_scans_do_not_construct_language_specific_indexes(self):
        self.assertEqual(indexes(ParsedRepository([])), {})
        self.assertEqual(
            indexes(repository("typescript", {"main.ts": "function run() {}"})), {}
        )

    def test_indexes_are_owned_by_each_repository(self):
        first = repository(
            "rust", {"main.rs": "mod tools;", "tools.rs": "pub fn run() {}"}
        )
        second = repository("rust", {"main.rs": "fn run() {}"})
        a, b = indexes(first), indexes(second)
        self.assertEqual(set(a), {"rust"})
        self.assertEqual(set(b), {"rust"})
        a_index, b_index = a["rust"], b["rust"]
        assert isinstance(a_index, RustModules) and isinstance(b_index, RustModules)
        self.assertIsNot(a_index, b_index)
        self.assertEqual(
            [file.source.path for file in a_index.rust_files("crate::tools")],
            ["tools.rs"],
        )
        self.assertEqual(b_index.rust_files("crate::tools"), [])


if __name__ == "__main__":
    unittest.main()
