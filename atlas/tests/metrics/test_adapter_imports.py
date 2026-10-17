"""Import policies distinguish namespaces, runtime exports and type-only names."""

from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import elixir, go, java, javascript, kotlin, rust
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from atlas.metrics.resolution_contract import ImportRequest
from tests.metrics.adapter_support import node, parsed, symbol, syntax


@pytest.fixture
def import_context():
    target = symbol("run")
    default = symbol("Default")
    calls = []

    def members(request, name):
        calls.append((request.path, name))
        return {"run": [target], "default": [default]}.get(name, [])

    return SimpleNamespace(
        _members=members, calls=calls, target=target, default=default
    )


@pytest.mark.parametrize(
    ("source", "expected", "lookups"),
    [
        (
            "import {run as execute, missing} from './tools'",
            [("execute", "target"), ("missing", None)],
            ["run", "missing"],
        ),
        (
            "import {type run, missing} from './tools'",
            [("run", None), ("missing", None)],
            ["missing"],
        ),
        ("import type {run as execute} from './tools'", [("execute", None)], []),
        (
            "import Default, {run} from './tools'",
            [("run", "target"), ("Default", "default")],
            ["run", "default"],
        ),
        ("import type Default from './tools'", [("Default", None)], []),
        ("import './tools'", [], []),
    ],
)
def test_script_import_aliases_resolve_runtime_members_only(
    import_context, source, expected, lookups
):
    result = javascript.JavaScriptResolution().import_item(
        import_context, ImportRequest(parsed(), "./tools", source=source)
    )
    assert result == [
        (name, [getattr(import_context, key)] if key else [], False)
        for name, key in expected
    ]
    assert import_context.calls == [("./tools", name) for name in lookups]


@pytest.mark.parametrize(("all_type", "expected"), [(True, True), (False, False)])
def test_script_type_only_named_import_requires_every_specifier(all_type, expected):
    entries = [
        node("import_specifier", children=[node("type")]),
        node("import_specifier", children=[node("type" if all_type else "identifier")]),
    ]
    directive = node(
        "import_statement",
        children=[
            node("import_clause", children=[node("named_imports", children=entries)])
        ],
    )
    assert javascript.JavaScriptResolution().import_type_only(directive) is expected
    assert javascript.JavaScriptResolution().import_type_only(None) is False


def test_script_exports_use_aliases_default_and_deduplicate_symbols():
    public = symbol("run", start=10, end=20)
    private = symbol("hidden", start=30, end=40)
    file = parsed(symbols=[public, private])

    def specifier():
        return node(
            "export_specifier", name=node(value="run"), alias=node(value="execute")
        )

    exports = [
        node(
            "export_statement",
            "export {run as execute}",
            children=[node("export_clause", children=[specifier(), specifier()])],
        ),
        node(
            "export_statement",
            "export default run",
            declaration=node(value="run", start=10, end=20),
        ),
        node(
            "export_statement",
            "export type {hidden}",
            children=[
                node(
                    "export_clause",
                    children=[node("export_specifier", name=node(value="hidden"))],
                )
            ],
        ),
        node(
            "export_statement",
            "export {hidden} from './other'",
            source=node(value="./other"),
        ),
    ]
    assert javascript.export_bindings(file, syntax(nodes=exports)) == {
        "execute": [public],
        "default": [public],
    }


@pytest.mark.parametrize(
    ("adapter", "source", "path", "alias"),
    [
        (java.JavaResolution(), "import pkg.Type;", "pkg.Type", "Type"),
        (kotlin.KotlinResolution(), "import pkg.Type as Local", "pkg.Type", "Local"),
        (elixir.ElixirResolution(), "alias Pkg.Type, as: Local", "Pkg.Type", "Local"),
    ],
)
def test_declared_imports_keep_alias_and_non_namespace_semantics(
    adapter, source, path, alias
):
    target = symbol("Type", kind="class")
    calls = []

    def declared(file, name):
        calls.append((file, name))
        return [target]

    file = parsed()
    ctx = SimpleNamespace(modules=SimpleNamespace(declared=declared))
    assert adapter.import_item(ctx, ImportRequest(file, path, source=source)) == [
        (alias, [target], False)
    ]
    assert calls == [(file, path)]


@pytest.mark.parametrize("count", [0, 1, 2])
@pytest.mark.parametrize("adapter", [java.JavaResolution(), elixir.ElixirResolution()])
def test_declared_import_key_requires_exactly_one_target(adapter, count):
    targets = [symbol(start=10 + i * 10) for i in range(count)]
    ctx = SimpleNamespace(modules=SimpleNamespace(declared=lambda file, name: targets))
    assert adapter.import_key(ctx, ImportRequest(parsed(), "pkg.Type")) == (
        targets[0].key if count == 1 else None
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [('alias "pkg/tools"', "alias"), ('"pkg/tools"', "tools"), ('. "pkg/tools"', None)],
)
def test_go_import_namespace_includes_only_top_level_symbols(source, expected):
    public = symbol("Run", path="tools.go")
    nested = symbol("nested", path="tools.go", parent=public.key)
    target = parsed("tools.go", "go", symbols=[public, nested])
    ctx = SimpleNamespace(path_files=lambda file, path: [target])
    result = go.GoResolution().import_item(
        ctx, ImportRequest(parsed(), "pkg/tools", source=source)
    )
    assert result == ([(expected, [public], True)] if expected else [])


@pytest.mark.parametrize("namespace", [False, True])
def test_rust_use_alias_distinguishes_module_from_member(namespace):
    file = parsed("lib.rs", "rust")
    target = symbol("Run", path="tools.rs")
    index = SimpleNamespace(
        rust_key=lambda file, path, position: "module:tools" if namespace else None,
        rust_symbols=lambda file, path, position: [target],
    )
    calls = []

    def members(request, name):
        calls.append((request.path, request.position, name))
        return [target]

    ctx = SimpleNamespace(
        modules=SimpleNamespace(indexes={"rust": index}), _members=members
    )
    result = rust.RustResolution().import_item(
        ctx,
        ImportRequest(file, "crate::tools::Run", 25, "use crate::tools::Run as Local;"),
    )
    assert result == [("Local", [target], namespace)]
    assert calls == ([] if namespace else [("crate::tools", 25, "Run")])


def test_unresolved_import_target_remains_explicit():
    ctx = SimpleNamespace(path_files=lambda file, path: [])
    assert ResolutionAdapter().import_targets(
        ctx, ImportRequest(parsed(), "missing")
    ) == [("missing", None)]
