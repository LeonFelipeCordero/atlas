"""Repository indexes are constructed only by adapters present in a scan."""

from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.resolution import Modules
from atlas.metrics.adapters.rust import RustModules
from atlas.metrics.resolution_syntax import Syntax
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources


def indexes(repo):
    return Modules(
        repo,
        {file.source.path: Syntax(file, get_resolution_adapter(file.source.language))
         for file in repo.files},
    ).indexes


@pytest.mark.parametrize("language", [None, "typescript", "java", "go", "elixir"])
def test_unrelated_scans_do_not_construct_language_specific_indexes(language):
    repo = parse_files(coffee_sources(language)) if language else ParsedRepository([])
    before = asdict(repo)
    with patch("atlas.metrics.adapters.rust.RustModules", side_effect=AssertionError):
        assert indexes(repo) == {}
    assert asdict(repo) == before


def assert_index_file_ownership(index, identity, path):
    file, = index.rust_files(identity)
    assert file.source.path == path
    assert file is next(file for file in index.repository.files if file.source.path == path)
    return file


def assert_distinct_index_files(indexes, identity, path):
    first, second = indexes
    a_file = assert_index_file_ownership(first, identity, path)
    b_file = assert_index_file_ownership(second, identity, path)
    assert a_file is not b_file
    assert a_file.source.absolute_path != b_file.source.absolute_path


def test_indexes_are_owned_by_each_repository(tmp_path):
    sources = coffee_sources("rust")
    first = parse_files(sources)
    second = parse_files([
        replace(source, absolute_path=tmp_path / source.path) for source in sources
    ])
    before = asdict(first), asdict(second)
    a, b = indexes(first), indexes(second)
    assert set(a) == set(b) == {"rust"}
    a_index, b_index = a["rust"], b["rust"]
    assert isinstance(a_index, RustModules) and isinstance(b_index, RustModules)
    assert a_index is not b_index
    assert a_index.repository is first and b_index.repository is second
    for identity, path in [
        ("crate::brewing::recipe", "brewing/recipe.rs"),
        ("crate::reporting::daily::totals", "reporting/daily/totals.rs"),
    ]:
        assert_distinct_index_files((a_index, b_index), identity, path)
    assert a_index.rust_files("crate::missing") == b_index.rust_files("crate::missing") == []
    assert (asdict(first), asdict(second)) == before
    a_index._scopes.clear()
    assert a_index.rust_files("crate::brewing::recipe") == []
    assert [file.source.path for file in b_index.rust_files("crate::brewing::recipe")] == [
        "brewing/recipe.rs"
    ]
