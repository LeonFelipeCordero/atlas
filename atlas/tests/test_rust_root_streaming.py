"""Fallback Rust roots must merge reference sets without retaining every traversal."""

import weakref

from atlas.adapters import get_resolution_adapter
from atlas.adapters.rust import RustModules
from atlas.extraction.resolution_syntax import Syntax
from tests.test_semantic_resolution import repository


def test_fallback_root_references_are_merged_incrementally(monkeypatch):
    repo = repository("rust", {
        "root.rs": "mod child;",
        "child.rs": "mod leaf;",
        "child/leaf.rs": "pub fn leaf() {}",
    })
    syntax = {
        file.source.path: Syntax(file, get_resolution_adapter("rust"))
        for file in repo.files
    }
    references: list[weakref.ReferenceType[set[str]]] = []
    original = RustModules._referenced_files

    def referenced_files(modules, root):
        # Argument expansion would keep earlier traversal sets alive here.
        assert not any(reference() is not None for reference in references)
        result = original(modules, root)
        references.append(weakref.ref(result))
        return result

    monkeypatch.setattr(RustModules, "_referenced_files", referenced_files)
    modules = RustModules(repo, syntax)
    assert len(references) == 2
    assert set(modules._file_scopes) == {"root.rs", "child.rs", "child/leaf.rs"}
