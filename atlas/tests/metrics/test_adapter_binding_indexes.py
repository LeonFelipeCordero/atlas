"""Build real adapter indexes from domain records and stub syntax, not parsers."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import Import, ParsedRepository
from atlas.metrics.adapters import go, java, javascript, rust
from atlas.metrics.adapters.resolution import (
    Binding,
    CallableIdentity,
    ImportBindings,
    Modules,
)
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


@pytest.mark.parametrize("scoped", [True, False])
@pytest.mark.parametrize("namespace", [True, False])
def test_generic_directive_bindings_keep_scope_and_top_level_members(scoped, namespace):
    adapter = ResolutionAdapter()
    member = symbol("run", path="pkg/tools.py")
    nested = symbol("hidden", path="pkg/tools.py", parent=member.key)
    target = parsed("pkg/tools.py", symbols=[member, nested])
    file = parsed("main.py", imports=[Import("main.py", "import tools", 1)])
    scope = node("block", start=20, end=80) if scoped else None
    adapter.paths = lambda source, name, files: [target]
    if not namespace:
        adapter.import_item = lambda ctx, request: [
            ("run", ctx._members(request, "run"), False)
        ]
    cache = {
        f.source.path: syntax(
            file=f,
            adapter=adapter,
            import_node=lambda line, source: None,
            import_scope=lambda line, source: scope,
        )
        for f in [file, target]
    }
    repository = ParsedRepository([file, target])
    index = ImportBindings(repository, cache, Modules(repository, cache))
    name = "tools" if namespace else "run"
    start, end = (20, 80) if scoped else (0, 200)
    binding = index.get(file, name, 50)
    assert binding == Binding(
        name,
        [member],
        namespace,
        start,
        end,
        scope=scope,
    )
    assert binding is not None
    assert binding.member("hidden") == []


@pytest.mark.parametrize("directive", [True, False])
def test_required_rust_import_syntax_prevents_phantom_use_binding(directive):
    file = parsed(
        "src/lib.rs", "rust", imports=[Import("src/lib.rs", "use crate as root", 1)]
    )
    root = node("source_file")
    imported = node("use_declaration", start=5)
    cache = {
        file.source.path: syntax(
            adapter=rust.RustResolution(),
            root=root,
            import_node=lambda line, source: imported if directive else None,
            import_scope=lambda line, source: None,
        )
    }
    repository = ParsedRepository([file])
    index = ImportBindings(repository, cache, Modules(repository, cache))
    assert index.bindings[file.source.path] == (
        [Binding("root", [], True, 0, 200)] if directive else []
    )


@pytest.mark.parametrize("package", ["pkg", ""])
def test_java_module_index_uses_package_and_nested_terminal_name(package):
    target = symbol(
        "Inner",
        path="Type.java",
        language="java",
        kind="class",
        qualified_name="Outer::Inner",
    )
    foreign = symbol("Inner", path="Type.kt", language="kotlin", kind="class")
    file = parsed("Type.java", "java", symbols=[target])
    other = parsed("Type.kt", "kotlin", symbols=[foreign])
    adapter = java.JavaResolution()
    cache = {
        f.source.path: syntax(
            adapter=adapter,
            nodes=[node("package_declaration", f"package {package};")]
            if package
            else [],
        )
        for f in [file, other]
    }
    index = Modules(ParsedRepository([file, other]), cache)
    assert index.same_package(file, "Inner") == [target]
    assert index.declared(file, "pkg.Inner" if package else "Inner") == [target]


@pytest.mark.parametrize(
    "variant", ["same", "different_directory", "different_package", "foreign"]
)
def test_go_package_members_require_directory_language_and_package_name(variant):
    parent = symbol("Owner", path="pkg/type.go", language="go", kind="type")
    method = symbol(
        "Run",
        path="other/method.go" if variant == "different_directory" else "pkg/method.go",
        language="go",
        kind="method",
    )
    file = parsed(parent.file_path, "go", symbols=[parent])
    other = parsed(
        method.file_path, "python" if variant == "foreign" else "go", symbols=[method]
    )
    declaration = node(
        "method_declaration",
        receiver=node(
            "parameter_list",
            children=[
                node("parameter_declaration", type=node("type_identifier", "Owner"))
            ],
        ),
    )
    adapter = go.GoResolution()
    cache = {
        f.source.path: syntax(
            file=f,
            adapter=adapter,
            nodes=[
                node(
                    "package_clause",
                    "package other"
                    if f is other and variant == "different_package"
                    else "package pkg",
                )
            ],
            declarations={(10, 20): declaration},
        )
        for f in [file, other]
    }
    resolver = SimpleNamespace(
        syntax=cache, files={f.source.path: f for f in [file, other]}
    )
    assert adapter.instance_members(resolver, parent, "Run") == (
        [method] if variant == "same" else []
    )
    assert adapter.same_package(resolver, file, "Owner") == [parent]


@pytest.mark.parametrize("shadowed", [True, False])
@pytest.mark.parametrize("lexical", [True, False])
def test_namespace_inheritance_requires_unshadowed_namespace(shadowed, lexical):
    base = symbol("Base", kind="class")
    binding = Binding("tools", [base], True, 0, 200)
    resolver = SimpleNamespace(
        imports=SimpleNamespace(get=lambda *args: binding),
        lexical=lambda *args: [base] if lexical else [],
        syntax={"src/main.py": syntax(shadowed=lambda *args: shadowed)},
    )
    query = request(name="tools.Base")
    assert ResolutionAdapter().inheritance(resolver, query, []) == (
        [] if shadowed or lexical else [base]
    )


@pytest.mark.parametrize("count", [0, 1, 2])
def test_default_callable_identity_keeps_only_unique_candidate(count):
    file = parsed()
    adapter = ResolutionAdapter()
    targets = [symbol(start=10 + i) for i in range(count)]
    identity = CallableIdentity(
        ParsedRepository([file]), {file.source.path: syntax(adapter=adapter)}
    )
    assert identity.select(file, request(file).call, targets) == (
        targets if count == 1 else []
    )


@pytest.mark.parametrize("type_only", [True, False])
def test_script_import_binding_preserves_public_namespace_map(type_only):
    adapter = javascript.JavaScriptResolution()
    exported = symbol("internal", path="src/tools.js")
    file = parsed(
        "src/main.js",
        "javascript",
        imports=[
            Import(
                "src/main.js",
                "import "
                + ("type " if type_only else "")
                + "* as tools from './tools'",
                1,
            )
        ],
    )
    target = parsed("src/tools.js", "javascript", symbols=[exported])
    export = node(
        "export_statement",
        children=[
            node(
                "export_clause",
                children=[
                    node(
                        "export_specifier",
                        name=node(value="internal"),
                        alias=node(value="public"),
                    )
                ],
            )
        ],
    )
    cache = {
        f.source.path: syntax(
            file=f,
            adapter=adapter,
            nodes=[export] if f is target else [],
            import_node=lambda *args: None,
            import_scope=lambda *args: None,
        )
        for f in [file, target]
    }
    repository = ParsedRepository([file, target])
    bindings = ImportBindings(repository, cache, Modules(repository, cache))
    selected = bindings.get(file, "tools", 50)
    assert selected == Binding(
        "tools",
        [] if type_only else [exported],
        True,
        0,
        200,
        members={} if type_only else {"public": [exported]},
    )
