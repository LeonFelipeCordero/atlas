"""Python package indexing and runtime import precedence with syntax stubs."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.python import PythonResolution
from atlas.metrics.resolution_contract import ImportRequest
from tests.metrics.adapter_support import node, parsed, symbol, syntax


@pytest.fixture
def package_context():
    adapter = PythonResolution()
    caller = parsed("app.py")
    member = symbol("run", path="pkg/tools.py")
    child = parsed("pkg/tools.py", symbols=[member])
    package = parsed("pkg/__init__.py")
    root = node("module")
    state = syntax(root=root, adapter=adapter, file=package, scope=lambda n: root)
    files = {"pkg": [package], "pkg.tools": [child]}
    members = {}
    ctx = SimpleNamespace(
        syntax={package.source.path: state, caller.source.path: syntax()},
        files=lambda source, path: files.get(path, []),
        _members=lambda request, name: members.get(name, []),
        modules=SimpleNamespace(indexes={"python": files}),
    )
    return adapter, ctx, caller, package, child, state, members


@pytest.mark.parametrize("root", ["src", "lib", ""])
def test_python_module_index_discovers_package_roots_and_filters_languages(root):
    prefix = root + "/" if root else ""
    package = parsed(prefix + "pkg/__init__.py")
    child = parsed(prefix + "pkg/tools.py")
    foreign = parsed(prefix + "pkg/other.py", "javascript")
    stub = parsed(prefix + "pkg/types.pyi")
    index = PythonResolution().module_index(
        ParsedRepository([package, child, foreign, stub]), {}
    )
    expected = {"pkg": [package], "pkg.tools": [child]}
    if root:
        expected.update({f"{root}.pkg": [package], f"{root}.pkg.tools": [child]})
    assert index == expected


@pytest.mark.parametrize("path", ["pkg", "pkg.tools", "missing"])
def test_python_absolute_import_uses_unique_index_identity(package_context, path):
    adapter, ctx, caller, package, child, _, _ = package_context
    assert (
        adapter.import_files(ctx, ImportRequest(caller, path))
        == {"pkg": [package], "pkg.tools": [child], "missing": []}[path]
    )


def package_attribute(package_context, kind):
    _, _, caller, package, _, state, members = package_context
    imported = symbol("tools", path=package.source.path)
    if kind == "member":
        members["tools"] = [imported]
    elif kind in {"assignment", "annotation"}:
        declaration = node(
            "assignment",
            **({"right": node(value="value")} if kind == "assignment" else {}),
        )
        state.bindings = [("tools", state.root, declaration)]
    elif kind in {"import", "nested_import", "excluded_import"}:
        directive = node(
            "import_statement", start=40, name=[node("dotted_name", "tools")]
        )
        state.nodes = [directive]
        if kind == "nested_import":
            state.scope = lambda n: node("function_definition")
        if kind == "excluded_import":
            caller = package
    elif kind == "module_file":
        package.source.path = "pkg.py"
    return caller, imported


@pytest.mark.parametrize(
    "kind",
    [
        "member",
        "assignment",
        "annotation",
        "import",
        "nested_import",
        "excluded_import",
        "none",
        "module_file",
    ],
)
def test_python_from_import_child_yields_to_runtime_package_attributes(
    package_context, kind
):
    adapter, ctx, _, _, child, _, _ = package_context
    caller, imported = package_attribute(package_context, kind)
    position = 40 if kind == "excluded_import" else 10
    result = adapter._from_import_item(
        ctx, ImportRequest(caller, "pkg", position), ("tools", "local")
    )
    child_visible = kind in {"annotation", "nested_import", "excluded_import", "none"}
    assert result == (
        "local",
        [imported] if kind == "member" else child.symbols if child_visible else [],
        child_visible,
    )


@pytest.mark.parametrize("bare", [True, False])
@pytest.mark.parametrize("member_count", [0, 1, 2])
def test_python_relative_from_target_prefers_unique_member_key(
    package_context, bare, member_count
):
    adapter, ctx, caller, _, _, _, members = package_context
    targets = [symbol("tools", start=10 + i) for i in range(member_count)]
    members["tools"] = targets
    path = "." if bare else "pkg"
    source = "from . import tools" if bare else "from pkg import tools"
    # A bare relative path resolves against the same package in this isolated context.
    original_files = ctx.files
    ctx.files = lambda file, name: original_files(
        file, {".": "pkg", ".tools": "pkg.tools"}.get(name, name)
    )
    result = adapter._from_import_target(
        ctx, ImportRequest(caller, path, source=source), "tools"
    )
    if bare:
        key = targets[0].key if member_count == 1 else None
        expected = (".tools", "file:pkg/tools.py" if member_count == 0 else key)
    else:
        expected = (
            ("pkg.tools", "file:pkg/tools.py")
            if member_count == 0
            else ("pkg", "file:pkg/__init__.py")
        )
    assert result == expected


@pytest.mark.parametrize("from_import", [True, False])
def test_python_import_directives_extract_aliases_targets_and_lexical_names(
    package_context, from_import
):
    adapter, ctx, caller, package, child, _, _ = package_context
    alias = node(
        "aliased_import",
        "pkg.tools as local",
        name=node("dotted_name", "tools" if from_import else "pkg.tools"),
        alias=node(value="local"),
    )
    directive = node(
        "import_from_statement" if from_import else "import_statement",
        start=25,
        name=[alias],
    )
    root = node("module")
    ctx.syntax[caller.source.path] = syntax(
        nodes=[node("expression"), directive], scope=lambda n: root
    )
    query = ImportRequest(
        caller,
        "pkg",
        25,
        "from pkg import tools as local"
        if from_import
        else "import pkg.tools as local",
    )
    assert adapter.import_item(ctx, query) == [
        ("local" if from_import else "local", child.symbols, True)
    ]
    assert adapter.import_targets(ctx, query) == [("pkg.tools", "file:pkg/tools.py")]
    assert adapter.lexical_imports(ctx.syntax[caller.source.path]) == [("local", root)]


def test_python_import_without_matching_syntax_does_not_invent_bindings(
    package_context,
):
    adapter, ctx, caller, _, _, _, _ = package_context
    query = ImportRequest(caller, "pkg", 99)
    assert adapter.import_item(ctx, query) == []
    assert adapter.import_targets(ctx, query) == [("pkg", "file:pkg/__init__.py")]


def test_python_plain_dotted_import_binds_module_namespace_and_root_lexical_name(
    package_context,
):
    adapter, ctx, caller, _, child, _, _ = package_context
    directive = node(
        "import_statement", start=25, name=[node("dotted_name", "pkg.tools")]
    )
    root = node("module")
    ctx.syntax[caller.source.path] = syntax(nodes=[directive], scope=lambda n: root)
    assert adapter.import_item(ctx, ImportRequest(caller, "pkg.tools", 25)) == [
        ("pkg.tools", child.symbols, True)
    ]
    assert adapter.lexical_imports(ctx.syntax[caller.source.path]) == [("pkg", root)]
