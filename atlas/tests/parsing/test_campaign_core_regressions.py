"""Real grammar cases for shared parsing campaign survivors."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from tree_sitter_language_pack import get_parser

from atlas.domain.models import SourceFile
from atlas.language_syntax import _declaration_head
from atlas.parsing import syntax
from atlas.parsing.adapters.kotlin import INHERITANCE as KOTLIN_INHERITANCE
from atlas.parsing.mutation_candidates import extract_candidates
from atlas.parsing.structure import _span_changed
from atlas.syntax import text, walk


def tree(language, source):
    return get_parser(language).parse(source.encode()).root_node


def candidates(language, source):
    return extract_candidates(SourceFile(path="sample", absolute_path=Path("sample"), language=language, source=source.encode())).candidates


@pytest.mark.parametrize("source,expected", [
    ("def f(x), do: x", "f(x)"),
    ("def f(x) when x > 0, do: x", "f(x)"),
    ("def a + b, do: {a, b}", "a + b"),
])
def test_elixir_declaration_head_keeps_unguarded_calls(source, expected):
    root = tree("elixir", source)
    assert text(_declaration_head(root.named_children[0])) == expected


def test_named_operand_is_not_an_operator():
    sites = candidates("javascript", "const value = left + and;")
    assert [(s.kind, s.originalText) for s in sites] == [("arithmetic", "+")]


def test_qualified_elixir_if_is_not_a_kernel_condition():
    sites = candidates("elixir", "Kernel.if(x, do: a + b)")
    assert [(s.kind, s.originalText) for s in sites] == [("arithmetic", "+")]


def test_kotlin_callable_name_is_not_anonymous():
    sites = candidates("kotlin", "fun sum(x: Int): Int { return x + 1 }")
    assert len(sites) == 1
    assert sites[0].callable is not None
    assert sites[0].callable.name == "sum"


def test_elixir_module_attributes_do_not_produce_runtime_mutations():
    assert candidates("elixir", "defmodule Config do\n @value (left + right)\nend") == []


def test_elixir_stab_body_is_not_a_pattern():
    sites = candidates("elixir", "case x do\n a + b -> c + d\nend")
    assert [(s.kind, s.expressionText) for s in sites] == [("arithmetic", "c + d")]


def test_span_change_checks_each_endpoint_and_missing_span():
    from tree_sitter_language_pack import Span

    node = tree("python", "x = 1").named_children[0]
    span = Span(start_byte=node.start_byte, end_byte=node.end_byte, start_line=0, start_column=0, end_line=0, end_column=5)
    assert not _span_changed(node, span)
    assert _span_changed(node, None)
    assert _span_changed(node, replace(span, start_byte=1))
    assert _span_changed(node, replace(span, end_byte=4))


@pytest.mark.parametrize("case", [
    ("kotlin", "class C : foo.Base<Int>() {}", KOTLIN_INHERITANCE, ["foo.Base"]),
    ("python", "class C(Base[T]): pass", syntax.InheritancePolicy(frozenset(), superclass_field="superclasses"), ["Base"]),
    ("typescript", "class C extends Base<T> {}", syntax.DEFAULT_POLICY, ["Base"]),
    ("java", "class C extends Base<String> {}", syntax.DEFAULT_POLICY, ["Base"]),
    ("java", "class C extends Outer<String>.Inner<Integer> {}", syntax.DEFAULT_POLICY, ["Outer.Inner"]),
])
def test_parameterized_inheritance_names(case):
    language, signature, policy, expected = case
    assert syntax.inheritance_names(syntax.DeclarationHeader(language, "class", signature), policy) == expected


def test_inheritance_constructor_without_fields_keeps_qualified_base():
    root = tree("kotlin", "class C : foo.Base<Int>() {}")
    assert not root.has_error
    constructor = next(n for n in walk(root) if n.type == "constructor_invocation")
    assert syntax._base_name(constructor, syntax.DEFAULT_POLICY) == "foo.Base"


@pytest.mark.parametrize("kind,signature", [("function", "class C(Base): pass"), ("class", "")])
def test_ineligible_header_never_parses(monkeypatch, kind, signature):
    parser = Mock()
    monkeypatch.setattr(syntax, "get_parser", parser)
    assert syntax.inheritance_names(syntax.DeclarationHeader("python", kind, signature)) == []
    parser.assert_not_called()


@pytest.mark.parametrize("signature,complete", [("class C", False), ("class C {}", True)])
def test_header_retry_requires_both_error_and_policy(monkeypatch, signature, complete):
    parser = get_parser("javascript")
    spy = Mock(wraps=parser)
    monkeypatch.setattr(syntax, "get_parser", lambda _: spy)
    syntax.inheritance_names(syntax.DeclarationHeader("javascript", "class", signature),
                             syntax.InheritancePolicy(frozenset(), complete_header=complete))
    assert spy.parse.call_count == 1


def test_generic_callee_keeps_name():
    root = tree("rust", "fn f(){ foo::<i32>(); }")
    call = next(n for n in walk(root) if n.type == "call_expression")
    assert syntax.call_target(call) == ("foo", True, None)
