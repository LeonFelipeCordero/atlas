"""Rust module mounts, path attributes, and scoped namespace bindings."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.rust import RustModules, RustResolution, path_attributes
from atlas.metrics.resolution_contract import ImportRequest
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


def attribute(value, name="path"):
    entry = node("attribute", children=[node(value=name), value])
    entry.child_by_field_name = lambda field: value if field == "value" else None
    return node("attribute_item", children=[entry])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (node("string_literal", '"alt/tools.rs"'), ["alt/tools.rs"]),
        (
            node(
                "raw_string_literal", children=[node("string_content", "alt/tools.rs")]
            ),
            ["alt/tools.rs"],
        ),
        (node("string_literal", '"unterminated'), []),
        (node("integer_literal", "42"), []),
    ],
)
def test_rust_path_attributes_decode_strings_but_reject_invalid_values(value, expected):
    declaration = node("mod_item")
    path = attribute(value)
    comment = node("line_comment")
    unrelated = attribute(node("string_literal", '"ignored"'), "cfg")
    declaration.prev_named_sibling = unrelated
    unrelated.prev_named_sibling = comment
    comment.prev_named_sibling = path
    assert path_attributes(declaration) == expected


@pytest.fixture
def inline_modules():
    file = parsed("src/lib.rs", "rust")
    nested = symbol(
        "nested",
        path=file.source.path,
        language="rust",
        kind="module",
        start=10,
        end=90,
    )
    direct = symbol(
        "run",
        path=file.source.path,
        language="rust",
        start=30,
        end=40,
        parent=nested.key,
    )
    file.symbols = [nested, direct]
    body = node(
        "declaration_list",
        start=20,
        end=80,
        children=[node("function_item", start=30, end=40)],
    )
    declaration = node(
        "mod_item", start=10, end=90, name=node(value="nested"), body=body
    )
    root = node("source_file", children=[declaration], end=200)
    cache = {file.source.path: syntax(file=file, root=root, nodes=[root, declaration])}
    index = RustModules(ParsedRepository([file]), cache)
    ctx = SimpleNamespace(
        modules=SimpleNamespace(indexes={"rust": index}), syntax=cache
    )
    return file, nested, direct, index, ctx


@pytest.mark.parametrize("name", ["crate::nested", "self::nested", "nested"])
def test_rust_inline_namespace_returns_direct_symbols_not_whole_file(
    inline_modules, name
):
    file, nested, direct, index, _ = inline_modules
    assert (
        index.rust_import(file, name),
        index.rust_key(file, name),
        index.rust_symbols(file, name),
    ) == ([], nested.key, [direct])


@pytest.mark.parametrize("name", ["self", "super", "super::nested", "super::super"])
def test_rust_relative_lookup_uses_inline_call_position(inline_modules, name):
    file, nested, direct, index, _ = inline_modules
    expected = {
        "self": (nested.key, [direct]),
        "super": ("file:src/lib.rs", [nested]),
        "super::nested": (nested.key, [direct]),
        "super::super": (None, []),
    }
    assert (
        index.rust_key(file, name, 35),
        index.rust_symbols(file, name, 35),
    ) == expected[name]


def test_rust_module_bindings_and_qualified_calls_share_scoped_symbols(inline_modules):
    file, _, direct, _, ctx = inline_modules
    adapter = RustResolution()
    bindings = adapter.module_bindings(ctx, file, 200)
    assert [(b.name, b.targets, b.namespace, b.start, b.end) for b in bindings] == [
        ("nested", [direct], True, 0, 200)
    ]
    assert adapter.qualified(
        ctx, request(file, qualifier="nested", start=100, end=110)
    ) == [direct]
    assert adapter.members(ctx, ImportRequest(file, "nested", 100), "missing") == []


@pytest.mark.parametrize("inline", [True, False])
def test_rust_path_attribute_overrides_default_module_directory(inline):
    root = parsed("src/lib.rs", "rust")
    child = parsed("src/custom/deep.rs" if inline else "src/custom.rs", "rust")
    deep = node("mod_item", name=node(value="deep"))
    body = (
        node("declaration_list", children=[deep], start=20, end=80) if inline else None
    )
    declaration = node(
        "mod_item", name=node(value="tools"), **({"body": body} if body else {})
    )
    declaration.prev_named_sibling = attribute(
        node("string_literal", '"custom"' if inline else '"custom.rs"')
    )
    cache = {
        root.source.path: syntax(root=node("source_file", children=[declaration])),
        child.source.path: syntax(root=node("source_file")),
    }
    index = RustModules(ParsedRepository([root, child]), cache)
    assert index.rust_import(
        root, "crate::tools::deep" if inline else "crate::tools"
    ) == [child]


@pytest.mark.parametrize("has_module", [True, False])
def test_rust_nonstandard_entry_inference_excludes_referenced_files(has_module):
    owner, child = parsed("src/owner.rs", "rust"), parsed("src/child.rs", "rust")
    modules = [node("mod_item", name=node(value="child"))] if has_module else []
    cache = {
        owner.source.path: syntax(root=node("source_file", children=modules)),
        child.source.path: syntax(root=node("source_file")),
    }
    index = RustModules(ParsedRepository([owner, child]), cache)
    assert index.rust_files("crate") == ([owner] if has_module else [])
    assert index.rust_files("crate::child") == ([child] if has_module else [])


@pytest.mark.parametrize("member_count", [0, 1, 2])
def test_rust_import_key_falls_back_to_unique_member(inline_modules, member_count):
    file, _, _, _, ctx = inline_modules
    targets = [symbol("item", start=i + 10) for i in range(member_count)]
    ctx._members = lambda request, name: (
        targets if request.path == "crate::nested" and name == "item" else []
    )
    assert RustResolution().import_key(
        ctx, ImportRequest(file, "crate::nested::item")
    ) == (targets[0].key if member_count == 1 else None)


@pytest.mark.parametrize("kind", ["mod_item", "struct_item", "missing"])
def test_rust_local_namespace_requires_module_syntax(kind):
    target = symbol()
    state = syntax(declarations={(10, 20): node(kind)} if kind != "missing" else {})
    resolver = SimpleNamespace(syntax={target.file_path: state})
    assert RustResolution().local_namespace(resolver, [target]) is (kind == "mod_item")


@pytest.mark.parametrize("self_kind", ["self_parameter", "pattern", "none"])
def test_rust_impl_function_staticness_requires_explicit_self(self_kind):
    method = symbol()
    parameters = (
        []
        if self_kind == "none"
        else [
            node("self_parameter")
            if self_kind == "self_parameter"
            else node("parameter", pattern=node("self"))
        ]
    )
    declaration = node(
        "function_item", parameters=node("parameters", children=parameters)
    )
    body = node("declaration_list", children=[declaration])
    node("impl_item", body=body)
    assert RustResolution().static(
        syntax(declarations={(10, 20): declaration}), method
    ) is (self_kind == "none")
