"""Receiver grammar and shared resolution mutation regressions."""

from types import SimpleNamespace
import pytest
from tree_sitter_language_pack import get_parser

from atlas import language_syntax
from atlas.metrics import receiver_syntax, resolver
from atlas.metrics.resolution_contract import DeclarationLookup
from atlas.metrics.resolution_syntax import names
from atlas.syntax import text, walk
from tests.metrics.resolution_support import node, symbol
from tests.metrics.test_resolution_syntax import syntax as syntax
from tests.metrics.test_receiver_ownership_regressions import resolver_for


def test_generic_type_without_name_field_uses_direct_type_identifier():
    generic = node("generic_type", children=[node("type_identifier", "Service"), node("type_arguments", "<T>")])

    assert receiver_syntax.type_name(generic) == "Service"


@pytest.mark.parametrize(("language", "source", "expected"), [
    ("java", "class C { Service service; static Service shared; }", [("service", False), ("shared", True)]),
    ("java", "class C { public final Service service; public static Service shared; }", [("service", False), ("shared", True)]),
    ("typescript", "class C { service: Service; static shared: Service; }", [("service", False), ("shared", True)]),
    ("kotlin", "class C(service: Service)", []),
    ("kotlin", "class C { val service = Service() }", [("service", False)]),
    ("kotlin", "class C { fun use() { val service = Service() } }", [("service", False)]),
    ("typescript", "class C { use(other: C) { other.service = new Service() } }", [("other", False)]),
    ("python", "class C:\n    def use(self, other):\n        other.service = Service()", []),
])
def test_receiver_bindings_on_real_class_grammars(language, source, expected):
    index = resolver_for(language, source)
    bindings = index.receivers.bindings["sample"]

    assert [(b.name, b.static) for b in bindings] == expected
    if language == "kotlin" and bindings:
        assert bindings[0].annotation == "Service"
        assert bindings[0].member is ("fun use" not in source)


@pytest.mark.parametrize(("start", "target", "expected"), [
    (10, "dependency", True), (19, "dependency", True), (20, "dependency", False),
    (9, "dependency", False), (15, "other", False),
])
def test_injected_parameter_write_scan_uses_name_and_half_open_method_span(start, target, expected):
    method = node("function_definition", start=10, end=20)
    write = node("assignment", start=start, end=start + 1, left=node(value=target))
    syntax = SimpleNamespace(nodes=[write], adapter=SimpleNamespace(assignments={"assignment"}))

    assert receiver_syntax._parameter_written(syntax, method, "dependency") is expected


def test_java_non_variable_node_with_parent_is_not_a_binding():
    declaration = node("identifier", "service")
    node("field_declaration", children=[declaration], type=node("type_identifier", "Service"))

    assert receiver_syntax.java_bindings(SimpleNamespace(), declaration) == []


@pytest.mark.parametrize("case", [(10, 100, True), (10, 101, False), (9, 20, False), (10, 20, True)])
def test_allowed_declaration_requires_both_containment_bounds(syntax, case):
    start, end, expected = case
    declaration = node("declaration", start=10, end=100)
    syntax.adapter.declaration_allowed.return_value = False

    assert syntax._declaration_allowed(DeclarationLookup("run", declaration, 50), [symbol(start=start, end=end)]) is expected


def test_named_declarator_is_not_a_go_multi_name_parameter():
    declaration = node("variable_declarator", name=node(value="service"))
    declaration.children_by_field_name = lambda name: [node(value="wrong")] if name == "name" else []

    assert names(declaration) == {"service"}


@pytest.mark.parametrize(("family", "expected"), [(None, "custom"), ("script", "script")])
def test_language_family_preserves_languages_without_family(monkeypatch, family, expected):
    monkeypatch.setattr(resolver, "get_resolution_adapter", lambda language: SimpleNamespace(family=family))

    assert resolver._language_family("custom") == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("def run(x) when is_integer(x), do: x", "run(x)"),
    (r"def run(x \\ 1), do: x", r"run(x \\ 1)"),
    ("def left + right, do: :ok", "left + right"),
])
def test_elixir_declaration_head_unwraps_only_when_guard(source, expected):
    root = get_parser("elixir").parse(source.encode()).root_node
    declaration = next(n for n in walk(root) if n.type == "call" and text(n.child_by_field_name("target")) == "def")

    assert text(language_syntax._declaration_head(declaration)) == expected
