"""Rust module, receiver, and call-target regressions for surviving mutations."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.rust import RustModules, RustResolution
from atlas.metrics.adapters.resolution import Binding
from atlas.metrics.resolution_contract import ImportRequest
from atlas.metrics.resolution_syntax import Syntax
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


def rust_modules(sources):
    files = [parsed(path, "rust") for path in sources]
    for file in files:
        file.source.source = sources[file.source.path].encode()
    states = {file.source.path: Syntax(file, RustResolution()) for file in files}
    return RustModules(ParsedRepository(files), states), files


@pytest.mark.parametrize("module_path", ["src/parent.rs", "src/parent/mod.rs"])
def test_external_module_children_use_correct_parent_directory(module_path):
    modules, files = rust_modules({"src/lib.rs": "mod parent;", module_path: "mod child;",
                                   "src/parent/child.rs": "pub fn run() {}"})
    assert modules.rust_files("crate::parent::child") == [files[2]]


@pytest.mark.parametrize("inline", [False, True])
def test_path_attributes_use_file_parent_or_inline_directory(inline):
    parent = 'mod parent { #[path = "custom.rs"] mod child; }' if inline else '#[path = "custom.rs"] mod child;'
    target = "src/parent/custom.rs" if inline else "src/custom.rs"
    modules, files = rust_modules({"src/lib.rs": parent, target: "pub fn run() {}"})
    assert modules.rust_files("crate::parent::child" if inline else "crate::child") == [files[1]]


def test_nonstandard_module_roots_require_a_module_declaration():
    modules, files = rust_modules({"src/entry.rs": "mod child;", "src/child.rs": "pub fn run() {}", 
                                   "src/unrelated.rs": "fn unrelated() {}"})
    assert modules.rust_files("crate") == [files[0]]
    assert modules.rust_files("crate::child") == [files[1]]


@pytest.mark.parametrize("case", [
    ("impl", "impl", False, True), ("struct", "impl", False, False),
    ("impl", "struct", False, False), ("impl", "impl", True, False),
])
def test_use_binding_replaces_only_impl_candidates(case):
    local_kind, match_kind, namespace, imported = case
    target = symbol("Owner", kind="struct")
    matches = [symbol("Owner", kind=match_kind)]
    resolver = SimpleNamespace(lexical=lambda *args: [symbol("Owner", kind=local_kind)],
                               imports=SimpleNamespace(get=lambda *args: Binding("Owner", [target], namespace, 0, 100)))
    assert RustResolution().qualify_class(resolver, request(), matches) == ([target] if imported else matches)


@pytest.mark.parametrize("ancestors", [[], [symbol(kind="function")], [symbol(kind="impl")]])
def test_receiver_owner_needs_both_function_and_impl(ancestors):
    resolver = SimpleNamespace(ancestors=lambda owner: ancestors)
    assert RustResolution().receiver_owner(resolver, request()) == []


@pytest.mark.parametrize("self_parameter", ["&self", "self", "self: Box<Self>", ""])
def test_receiver_owner_uses_self_taking_function_and_enclosing_impl(self_parameter):
    file = parsed("src/lib.rs", "rust")
    file.source.source = f"impl Owner {{ fn run({self_parameter}) {{}} }}".encode()
    state = Syntax(file, RustResolution())
    impl = next(n for n in state.nodes if n.type == "impl_item")
    method = next(n for n in state.nodes if n.type == "function_item")
    owner = symbol("Owner", path=file.source.path, kind="impl", start=impl.start_byte, end=impl.end_byte)
    function = symbol("run", path=file.source.path, kind="function", start=method.start_byte, end=method.end_byte)
    target = symbol("Owner", path=file.source.path, kind="struct")
    resolver = SimpleNamespace(ancestors=lambda ignored: [function, owner],
                               syntax={file.source.path: state})
    adapter = RustResolution()
    adapter._impl_types = lambda resolver, symbol, name: [target] if name == "Owner" else []
    assert adapter.receiver_owner(resolver, request(file)) == ([target] if self_parameter else [])
    assert adapter.static(state, function) is (not bool(self_parameter))


@pytest.mark.parametrize("kind", ["function_item", "identifier", "struct_item"])
def test_non_impl_syntax_uses_shared_static_policy(kind):
    declaration = node(kind)
    node("source_file", children=[declaration])
    assert not RustResolution().static(syntax(declarations={(10, 20): declaration}), symbol())


def test_no_use_binding_keeps_local_candidates():
    matches = [symbol(kind="impl")]
    resolver = SimpleNamespace(lexical=lambda *args: matches,
                               imports=SimpleNamespace(get=lambda *args: None))
    assert RustResolution().qualify_class(resolver, request(), matches) == matches


def test_trait_associated_function_does_not_use_impl_static_policy():
    declaration = node("function_item", parameters=node("parameters"))
    node("trait_item", body=node("declaration_list", children=[declaration]))
    assert not RustResolution().static(syntax(declarations={(10, 20): declaration}), symbol())


def test_non_function_impl_item_does_not_use_function_static_policy():
    declaration = node("const_item")
    node("impl_item", body=node("declaration_list", children=[declaration]))
    assert not RustResolution().static(syntax(declarations={(10, 20): declaration}), symbol(kind="constant"))
    assert not RustResolution().static(syntax(), symbol())


def test_missing_method_syntax_cannot_prove_self():
    method = symbol()
    resolver = SimpleNamespace(syntax={method.file_path: syntax()})
    assert not RustResolution()._has_self(resolver, method)


@pytest.mark.parametrize("kind", ["struct_expression", "call_expression"])
def test_struct_literal_target_does_not_confuse_ordinary_call_receiver(kind):
    name, receiver = node(value="Owner"), node(value="factory")
    expression = node(kind, name=name, object=receiver)
    assert RustResolution().call_target(expression) == (name, None if kind == "struct_expression" else receiver)
    assert RustResolution().call_target(None) == (None, None)


@pytest.mark.parametrize("qualifier", ["this", "self", "crate::Owner", "factory()", "", None])
@pytest.mark.parametrize("has_receiver", [False, True])
def test_receiver_rejection_requires_explicit_path_except_this(qualifier, has_receiver):
    receiver = node() if has_receiver else None
    assert RustResolution().receiver_rejected(receiver, qualifier) is (
        has_receiver and qualifier in {"self", "crate::Owner"})


@pytest.mark.parametrize("path, key", [("crate", None), ("crate::run", None), ("crate::run", "module:crate")])
def test_import_key_falls_back_to_members_only_for_unresolved_qualified_path(path, key):
    target = symbol()
    calls = []
    index = SimpleNamespace(rust_key=lambda *args: key)
    ctx = SimpleNamespace(modules=SimpleNamespace(indexes={"rust": index}),
                          _members=lambda request, name: calls.append((request.path, name)) or [target])
    result = RustResolution().import_key(ctx, ImportRequest(parsed(language="rust"), path))
    assert result == (key or (target.key if "::" in path else None))
    assert calls == ([("crate", "run")] if key is None and "::" in path else [])
