"""Supported grammar regressions from the completed adapter mutation review."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import base, elixir, generic, go, java, javascript, kotlin
from atlas.metrics.adapters.callable_selection import (
    TypeContext,
    call_arguments,
    callable_parameters,
    expression_type,
)
from atlas.metrics.resolution_syntax import Syntax
from atlas.parsing.parser import parse_file
from atlas.syntax import text
from tests.metrics.adapter_support import parsed, symbol


def source_syntax(language, source, adapter):
    file = parsed(
        f"src/main.{ {'javascript': 'js', 'kotlin': 'kt', 'elixir': 'ex', 'java': 'java', 'go': 'go'}[language] }",
        language,
    )
    file.source = replace(file.source, source=source.encode())
    state = Syntax(file, adapter)
    assert state.root is not None and not state.root.has_error
    return state


@pytest.mark.parametrize(
    "source", ["fun f() { run(1) { it } }", "fun f() { run { it } }"]
)
def test_kotlin_trailing_lambda_has_unknown_argument_shape(source):
    state = source_syntax("kotlin", source, kotlin.KotlinResolution())
    call = next(n for n in state.nodes if n.type == "call_expression")
    assert call_arguments(call) is None


def test_kotlin_named_and_positional_arguments_remain_distinct():
    state = source_syntax(
        "kotlin", "fun f() { run('x', label = true) }", kotlin.KotlinResolution()
    )
    call = next(n for n in state.nodes if n.type == "call_expression")
    arguments = call_arguments(call)
    assert arguments is not None
    assert [(text(a.value), a.name, a.spread) for a in arguments] == [
        ("'x'", None, False),
        ("true", "label", False),
    ]


@pytest.mark.parametrize(
    "case",
    [
        (
            "java",
            "class A { void f() { run('x', true, false); } }",
            "character_literal",
            "char",
        ),
        ("java", "class A { void f() { run('x', true, false); } }", "true", "boolean"),
        ("java", "class A { void f() { run('x', true, false); } }", "false", "boolean"),
        ("kotlin", "fun f() { run('x', true, false) }", "character_literal", "Char"),
        ("kotlin", "fun f() { run('x', true, false) }", "boolean_literal", "Boolean"),
    ],
)
def test_literal_type_proofs_follow_language(case):
    language, source, kind, expected = case
    state = source_syntax(
        language,
        source,
        java.JavaResolution() if language == "java" else kotlin.KotlinResolution(),
    )
    literal = next(n for n in state.nodes if n.type == kind)
    assert expression_type(TypeContext(state, set()), literal) == expected


def test_java_variadic_parameter_uses_variable_declarator_name():
    state = source_syntax(
        "java", "class A { void f(String... values) {} }", java.JavaResolution()
    )
    declaration = next(n for n in state.nodes if n.type == "method_declaration")
    parameters = callable_parameters(declaration)
    assert parameters is not None
    assert [(p.name, p.annotation, p.variadic) for p in parameters] == [
        ("values", "String", True)
    ]


def test_java_nested_if_is_not_an_alternative_but_else_if_is():
    state = source_syntax(
        "java",
        "class A { void f() { if (a) if (b) run(); else if (c) stop(); } }",
        java.JavaResolution(),
    )
    conditions = [n for n in state.nodes if n.type == "if_statement"]
    assert [base.alternative(n) for n in conditions] == [False, False, True]


def test_kotlin_else_if_requires_alternative_wrapper():
    state = source_syntax(
        "kotlin",
        "fun f() { if (a) { if (b) run() } else if (c) stop() }",
        kotlin.KotlinResolution(),
    )
    conditions = [n for n in state.nodes if n.type == "if_expression"]
    assert [kotlin.alternative(n) for n in conditions] == [False, False, True]
    # These real non-if nodes include root, control bodies, identifiers and calls.
    assert not any(
        kotlin.alternative(n) for n in state.nodes if n.type != "if_expression"
    )


def test_kotlin_if_inside_while_body_is_not_an_else_if():
    state = source_syntax(
        "kotlin", "fun f() { while (a) if (b) run() }", kotlin.KotlinResolution()
    )
    condition = next(n for n in state.nodes if n.type == "if_expression")
    assert condition.parent is not None
    assert condition.parent.type == "control_structure_body"
    assert condition.parent.parent is not None
    assert condition.parent.parent.type == "while_statement"

    assert kotlin.alternative(condition) is False


def test_generic_unwraps_nested_parentheses_but_preserves_calls_and_none():
    state = source_syntax(
        "javascript", "((service)).run();", javascript.JavaScriptResolution()
    )
    wrapper = next(n for n in state.nodes if n.type == "parenthesized_expression")
    assert text(generic.unwrapped(wrapper)) == "service"
    call = next(n for n in state.nodes if n.type == "call_expression")
    assert generic.unwrapped(call) == call
    assert generic.unwrapped(None) is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("left() |> right()", [0, 1]),
        ("left() + right()", [0, 0]),
        ("value |> right", [1]),
    ],
)
def test_elixir_pipeline_adds_input_only_to_right_operand(source, expected):
    state = source_syntax("elixir", source, elixir.ElixirResolution())
    operands = [n for n in state.nodes if n.type == "call"]
    if not operands:
        operands = [
            n for n in state.nodes if n.type == "identifier" and text(n) == "right"
        ]
    assert [elixir._call_arity(n) for n in operands] == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def run(x), do: x", 1),
        ("run(1)", None),
        ("run(inner(1))", None),
        ("value", None),
    ],
)
def test_elixir_parameter_count_accepts_declarations_not_invocations(source, expected):
    state = source_syntax("elixir", source, elixir.ElixirResolution())
    assert state.root is not None
    declaration = state.root.named_children[0]
    assert elixir.parameter_count(declaration) == expected


def test_elixir_recovered_clause_without_pattern_is_conservatively_refutable():
    from tree_sitter_language_pack import get_parser

    from atlas.syntax import walk

    root = get_parser("elixir").parse(b"case x do\n -> :ok\nend").root_node
    clause = next(n for n in walk(root) if n.type == "stab_clause")
    assert clause.child_by_field_name("left") is None

    assert elixir.clause_decision(clause) is True


def test_elixir_guarded_wildcard_is_refutable_but_plain_wildcard_is_not():
    state = source_syntax(
        "elixir",
        "case x do\n _ when x > 0 -> :yes\n _ -> :no\nend",
        elixir.ElixirResolution(),
    )
    clauses = [n for n in state.nodes if n.type == "stab_clause"]
    assert [elixir.clause_decision(n) for n in clauses] == [True, False]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "class Owner { run() {} } const a = Owner.prototype; const b = a; b.run = replacement;",
            True,
        ),
        (
            "class Owner { run() {} } const a = Owner.prototype; const b = a; b.other = replacement;",
            False,
        ),
        (
            "class Owner { run() {} } const box = {}; box.alias = Owner.prototype;",
            False,
        ),
        (
            "class Owner { run() {} } let alias; alias = Owner.prototype; alias.run = replacement;",
            True,
        ),
    ],
)
def test_javascript_prototype_alias_closure_ignores_non_identifier_targets(
    source, expected
):
    adapter = javascript.JavaScriptResolution()
    state = source_syntax("javascript", source, adapter)
    declaration = next(n for n in state.nodes if n.type == "class_declaration")
    parent = symbol(
        "Owner", kind="class", start=declaration.start_byte, end=declaration.end_byte
    )
    assert adapter.member_overwritten(state, parent, "run") is expected
    if "box.alias" in source:
        assignment = next(n for n in state.nodes if n.type == "assignment_expression")
        assert javascript._receiver_alias(assignment, {"Owner.prototype"}) is None


def test_javascript_var_scope_stops_at_function_not_its_parent():
    state = source_syntax(
        "javascript",
        "function f() { if (ok) { var inner = 1; let local = 2; } } var outer = 3;",
        javascript.JavaScriptResolution(),
    )
    bindings = {name: scope.type for name, scope, _ in state.bindings}
    assert bindings["inner"] == "function_declaration"
    assert bindings["local"] == "statement_block"
    assert bindings["outer"] == "program"


def test_go_competing_methods_require_both_name_and_receiver():
    adapter = go.GoResolution()
    state = source_syntax(
        "go",
        """package main
    type Owner struct{}
    type Other struct{}
    func (o Owner) Run() {}
    func (o Owner) Stop() {}
    func (o *Other) Run() {}
    func Run() {}
    """,
        adapter,
    )
    file = parse_file(state.file.source)
    state = Syntax(file, adapter)
    resolver = SimpleNamespace(
        files={file.source.path: file}, syntax={file.source.path: state}
    )
    owner = next(s for s in file.symbols if s.name == "Owner" and s.kind == "type")
    matches = adapter.instance_members(resolver, owner, "Run")
    assert len(matches) == 1
    assert matches[0].kind == "method"
    assert "(o Owner)" in text(state.node(matches[0].start_byte, matches[0].end_byte))
