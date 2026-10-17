"""Lexical and module indexes preserve scope and ambiguity at boundaries."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.generic import GenericResolution
from atlas.metrics.adapters.module_index import ModuleIndex, ModuleScope
from atlas.metrics.adapters.resolution import Binding, ImportBindings, Modules
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from atlas.metrics.adapters.rust import RustModules
from tests.metrics.adapter_support import node, parsed, symbol, syntax


@pytest.fixture
def lexical_bindings():
    file = parsed()
    adapter = ResolutionAdapter()
    cache = {file.source.path: syntax(adapter=adapter, file=file)}
    result = ImportBindings(
        ParsedRepository([file]), cache, Modules(ParsedRepository([file]), cache)
    )
    return file, result


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (0, "outer"),
        (19, "outer"),
        (20, "inner"),
        (39, "inner"),
        (40, "outer"),
        (99, "outer"),
        (100, None),
    ],
)
def test_import_binding_uses_narrowest_half_open_scope(
    lexical_bindings, position, expected
):
    file, index = lexical_bindings
    outer = Binding("tools", [symbol("outer")], True, 0, 100)
    inner = Binding("tools", [symbol("inner")], True, 20, 40)
    index.bindings[file.source.path] = [outer, inner]
    selected = index.get(file, "tools", position)
    assert ([s.name for s in selected.targets] if selected else None) == (
        [expected] if expected else None
    )


def test_equal_width_imports_are_explicitly_ambiguous_and_do_not_fall_back(
    lexical_bindings,
):
    file, index = lexical_bindings
    index.bindings[file.source.path] = [
        Binding("tools", [symbol()], True, 0, 100),
        Binding("tools", [symbol("one")], True, 20, 40),
        Binding("tools", [symbol("two")], True, 20, 40),
    ]
    assert index.get(file, "tools", 25) == Binding("tools", [], False, 0, 0)
    assert index.get(file, "missing", 25) is None


def test_invisible_scope_does_not_mask_visible_import(lexical_bindings):
    file, index = lexical_bindings
    outer = Binding("tools", [symbol()], True, 0, 100)
    index.bindings[file.source.path] = [
        outer,
        Binding("tools", [], True, 20, 40, scope=node()),
    ]
    index.syntax[file.source.path]._visible = lambda scope, position: False
    assert index.get(file, "tools", 25) is outer


def test_binding_explicit_export_map_overrides_declaration_names():
    target = symbol("internal")
    binding = Binding("tools", [target], True, 0, 100, members={"public": [target]})
    assert binding.member("public") == [target]
    assert binding.member("internal") == []
    assert Binding("tools", [target], True, 0, 100).member("internal") == [target]


def test_path_cache_filters_family_and_keys_by_source_and_path(lexical_bindings):
    file, index = lexical_bindings
    other = parsed("src/other.py")
    foreign = parsed("src/other.go", "go")
    index.repository.files.extend([other, foreign])
    index.syntax[other.source.path] = syntax(adapter=ResolutionAdapter())
    index.syntax[foreign.source.path] = syntax(adapter=SimpleNamespace(family="go"))
    calls = []

    def paths(source, name, files):
        calls.append((source.source.path, name, files))
        return [other]

    index.syntax[file.source.path].adapter.paths = paths
    assert index.path_files(file, "tools") == [other]
    assert index.path_files(file, "tools") == [other]
    assert calls == [(file.source.path, "tools", [file, other])]
    assert index.path_files(file, "different") == [other]
    assert len(calls) == 2


@pytest.fixture
def scoped_modules():
    file = parsed("lib.rs", "rust")
    root = ModuleScope(
        file, "crate", node("source_file", end=100), Path("/adapter-project")
    )
    body = node("declaration_list", start=20, end=40)
    node("mod_item", start=10, end=45, body=body)
    inner = ModuleScope(file, "crate::inner", body, Path("/adapter-project/inner"))
    index = ModuleIndex()
    index.add_scopes([root, inner])
    return file, index, root, inner


@pytest.mark.parametrize(
    ("position", "inner"),
    [(None, False), (19, False), (20, True), (39, True), (40, False)],
)
def test_module_scope_lookup_uses_narrowest_scope(scoped_modules, position, inner):
    file, index, root, nested = scoped_modules
    assert index.scopes_at(file, position) == [nested if inner else root]


def test_duplicate_module_identity_stays_ambiguous(scoped_modules):
    file, index, root, nested = scoped_modules
    assert index.unique_scope(["crate::inner"]) is nested
    assert index.unique_scope(["crate", "crate::inner"]) is None
    assert index.unique_scope(["missing"]) is None
    index.add_scopes([root])
    assert index.unique_scope(["crate"]) is None
    assert index.scope_files("crate") == []
    assert index.scope_files("crate::inner") == []


def test_inline_module_symbols_require_direct_child_spans(scoped_modules):
    file, index, root, inner = scoped_modules
    direct = symbol("direct", path="lib.rs", start=22, end=25, parent="module:inner")
    nested = symbol("nested", path="lib.rs", start=30, end=32, parent=direct.key)
    module = symbol("inner", path="lib.rs", start=10, end=45)
    file.symbols = [module, direct, nested]
    inner.body.named_children = [node("function_item", start=22, end=25)]
    assert index.scope_symbols(inner) == [direct]
    assert index.scope_symbols(root) == [module]
    assert index.scope_key(inner) == module.key
    assert index.scope_key(root) == "file:lib.rs"
    assert index.scope_symbols(None) == []


def test_walk_scopes_stops_external_file_cycles_but_keeps_inline_scopes(scoped_modules):
    file, index, root, inner = scoped_modules
    other = ModuleScope(
        parsed("other.rs", "rust"),
        "crate::other",
        node("source_file"),
        Path("/adapter-project"),
    )

    def children(scope):
        return [inner, other] if scope is root else [root] if scope is other else []

    assert list(index.walk_scopes(root, children)) == [root, other, inner]


@pytest.mark.parametrize("duplicate", [False, True])
def test_rust_external_module_lookup_rejects_both_file_layouts(duplicate):
    root = parsed("src/lib.rs", "rust")
    child = parsed("src/tools.rs", "rust", symbols=[symbol("run", path="src/tools.rs")])
    alternative = parsed("src/tools/mod.rs", "rust")
    files = [root, child] + ([alternative] if duplicate else [])
    cache = {f.source.path: syntax(file=f, root=node("source_file")) for f in files}
    cache[root.source.path].root = node(
        "source_file", children=[node("mod_item", name=node(value="tools"))]
    )
    index = RustModules(ParsedRepository(files), cache)
    assert index.rust_import(root, "crate::tools") == ([] if duplicate else [child])
    assert index.rust_symbols(root, "crate::tools") == (
        [] if duplicate else child.symbols
    )
    assert index.rust_key(root, "crate::tools") == (
        None if duplicate else "file:src/tools.rs"
    )
    assert index.rust_import(root, "super::tools") == []


def test_generic_call_target_unwraps_receiver_without_inventing_type_bindings():
    receiver = node(value="service")
    wrapped = node("parenthesized_expression", children=[receiver])
    callee = node(value="run")
    call = node("call_expression", function=callee, object=wrapped)
    adapter = GenericResolution("c")
    assert adapter.call_target(node("parenthesized_expression", children=[call])) == (
        callee,
        receiver,
    )
    assert adapter.receiver_bindings(None, call) == []
    cache = syntax(
        member_rebound=lambda name, member: name == "Service" and member == "run"
    )
    assert adapter.receiver_class_allowed(cache, node(value="Service"), "run") is False
    assert adapter.receiver_class_allowed(cache, node(value="Other"), "run") is True
