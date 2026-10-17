"""Parsing adapters: JSX boundaries, declaration carriers and Rust payloads."""

import pytest
from tree_sitter_language_pack import get_parser

from atlas.parsing.adapters import go, javascript, kotlin, python, rust
from atlas.parsing.syntax import callback_binding
from atlas.syntax import text, walk


def tree(language, source):
    return get_parser(language).parse(source.encode()).root_node


def node(language, source, kind):
    return next(n for n in walk(tree(language, source)) if n.type == kind)


@pytest.mark.parametrize("source,expected", [
    ("package p; func f(){ a, b := 1, func(){} }", "b"),
    ("package p; func f(){ use(func(){}) }", None),
    ("package p; func f() func(){ return func(){} }", None),
])
def test_go_literal_binding_uses_assignment_position_only(source, expected):
    literal = node("go", source, "func_literal")
    assert go.declaration(literal).name == expected


@pytest.mark.parametrize("tag", ["a", "z", "my-tag"])
def test_native_jsx_tags_are_not_components(tag):
    assert list(javascript.call_sites(tree("javascript", f"<{tag} />"))) == []


def test_callback_parentheses_ignore_comments():
    root = tree("javascript", "const f = (/* comment */ () => 1);")
    value = next(n for n in walk(root) if n.type == "variable_declarator")
    carrier = javascript.script_declaration(value)
    assert carrier.node.type == "arrow_function"
    assert carrier.name == "f"
    arrow = carrier.node
    assert callback_binding(arrow) == "f"


def test_uninitialized_binding_is_not_a_callback():
    binding = node("javascript", "let value;", "variable_declarator")
    carrier = javascript.script_declaration(binding)
    assert carrier.node == binding
    assert carrier.name == "value"


def test_python_decorated_definition_keeps_its_carrier_and_decorators():
    decorated = node("python", "@deco\ndef f(): pass", "decorated_definition")
    carrier = python.declaration(decorated)
    assert carrier.node.type == "function_definition"
    assert carrier.name == "f"
    assert carrier.decorators == ("@deco",)


def test_kotlin_base_name_only_accepts_user_type():
    root = tree("kotlin", "class C : foo.Base<Int>() {}")
    user_type = next(n for n in walk(root) if n.type == "user_type")
    assert kotlin._base_name(user_type) == "foo.Base"
    assert kotlin._base_name(root) is None


@pytest.mark.parametrize("declaration,macro,expected", [
    ("mod std {}", "std::println", False),
    ("mod other {}", "std::println", True),
    ("use other::std;", "std::println", False),
    ("extern crate custom as core;", "core::println", False),
    ("use std::fmt;", "std::println", True),
    ("extern crate std;", "std::println", True),
    ("use other::println;", "println", False),
    ("use other::*;", "println", False),
    ("use other::h;", "println", True),
    ("use std::println;", "println", True),
    ("macro_rules! println { () => {} }", "println", False),
    ("macro_rules! other { () => {} }", "println", True),
    ("", "other::println", False),
])
def test_rust_macro_evaluation_respects_namespace_and_shadowing(declaration, macro, expected):
    root = tree("rust", f"{declaration} fn f() {{ {macro}!(g()); }}")
    invocation = next(n for n in walk(root) if n.type == "macro_invocation")
    payloads = list(rust.macro_payloads(invocation))
    assert bool(payloads) is expected
    if expected:
        assert any(text(n) == "g()" for n in walk(payloads[0][0]))


@pytest.mark.parametrize("declaration,expected", [
    ("let g = value;", False),
    ("let other = value;", True),
    ("fn g() {}", False),
    ("fn other() {}", True),
    ("use other::g;", False),
    ("use other::*;", False),
    ("use other::h;", True),
])
def test_rust_payload_binding_rejects_only_matching_names(declaration, expected):
    root = tree("rust", f"fn f() {{ {declaration} g(); }}")
    call = next(n for n in walk(root) if n.type == "call_expression")
    assert rust.payload_unshadowed(call, "g") is expected


def test_rust_parameter_type_path_does_not_bind_module_name():
    root = tree("rust", "fn f(other: g::Type) { g(); }")
    call = next(n for n in walk(root) if n.type == "call_expression")
    assert rust.payload_unshadowed(call, "g")


def test_nested_rust_payload_checks_original_macro_bindings():
    source = "macro_rules! dbg { () => {} } fn f(){ println!(dbg!(g())); }"
    sites = list(rust.rust_call_sites(tree("rust", source)))
    assert [rust.rust_call_target(site)[0] for site in sites] == ["println!", "dbg!"]
