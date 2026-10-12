"""Fallback entry layout must release each coffee-module traversal before the next."""

import weakref
from dataclasses import asdict, replace

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.rust import RustModules
from atlas.metrics.resolution_syntax import Syntax
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources


def fallback_entry_sources():
    # Path-only operational overlay: every application byte remains shared.
    return [replace(source, path="coffee.rs", absolute_path=source.absolute_path.with_name("coffee.rs"))
            if source.path == "main.rs" else source for source in coffee_sources("rust")]


def test_fallback_root_references_are_merged_incrementally(monkeypatch):
    repo = parse_files(fallback_entry_sources())
    before = asdict(repo)
    syntax = {file.source.path: Syntax(file, get_resolution_adapter(file.source.language))
              for file in repo.files}
    references: list[weakref.ReferenceType[set[str]]] = []
    visited = []
    original = RustModules._referenced_files

    def referenced_files(modules, root):
        # Expanding traversal results as arguments would keep earlier sets alive.
        assert not any(reference() is not None for reference in references)
        visited.append(root.source.path)
        result = original(modules, root)
        references.append(weakref.ref(result))
        return result

    monkeypatch.setattr(RustModules, "_referenced_files", referenced_files)
    modules = RustModules(repo, syntax)
    assert set(visited) == {
        file.source.path for file in repo.files if modules._module_owner(file)
    }
    assert {"coffee.rs", "brewing/mod.rs", "reporting/mod.rs"} <= set(visited)
    assert len(references) == len(visited) >= 3
    assert all(reference() is None for reference in references)
    assert {
        "coffee.rs", "brewing/mod.rs", "brewing/brewer.rs", "brewing/recipe.rs",
        "brewing/inventory.rs", "reporting/mod.rs", "reporting/report.rs",
        "reporting/daily/totals.rs",
    } <= set(modules._file_scopes)
    assert asdict(repo) == before
