"""Shared syntax fallbacks preserve staticness, call spelling, and write targets."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import javascript, python
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from tests.metrics.adapter_support import node, request, symbol, syntax


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ("token", True),
        ("modifier", True),
        ("nonstatic", False),
        ("signature", True),
        ("signature_body", False),
        ("missing", False),
    ],
)
def test_static_detection_reads_tokens_or_signature_prefix_only(shape, expected):
    adapter = javascript.JavaScriptResolution()
    method = symbol(
        signature={
            "signature": "public static run()",
            "signature_body": "run(static value)",
        }.get(shape)
    )
    children = {
        "token": [node("static")],
        "modifier": [node("modifiers", "public static")],
        "nonstatic": [node("modifiers", "public nonstatic")],
    }
    declarations = (
        {(10, 20): node("method_definition", children=children[shape])}
        if shape in children
        else {}
    )
    assert adapter.static(syntax(declarations=declarations), method) is expected


@pytest.mark.parametrize("shape", ["fallback", "empty", "none"])
def test_call_fallback_uses_first_named_child_without_losing_original_spelling(shape):
    call = request(name="original", qualifier="service").call
    expression = (
        node("call", children=[node(value="actual")])
        if shape == "fallback"
        else node("call")
        if shape == "empty"
        else None
    )
    adapter = ResolutionAdapter()
    callee, receiver = adapter.call_target(expression)
    target = adapter.normalized_call(call, callee, receiver)
    assert (target.name, target.qualifier) == (
        "actual" if shape == "fallback" else "original",
        "service",
    )


@pytest.mark.parametrize("field_name", ["left", "argument", "operand", "fallback"])
def test_write_target_uses_explicit_fields_before_named_child(field_name):
    target = node(value="receiver.run")
    expression = (
        node("update_expression", **{field_name: target})
        if field_name != "fallback"
        else node("update_expression", children=[target])
    )
    assert ResolutionAdapter().write_target(expression) is target


@pytest.mark.parametrize("relationship", ["CALLS", "REFERENCES"])
def test_script_reference_normalization_preserves_recorded_target(relationship):
    call = replace(
        request(name="recorded", qualifier="Original").call, relationship=relationship
    )
    target = javascript.JavaScriptResolution().normalized_call(
        call, node(value="syntaxName"), node(value="syntaxOwner")
    )
    assert (target.name, target.qualifier) == (
        ("recorded", "Original")
        if relationship == "REFERENCES"
        else ("syntaxName", "syntaxOwner")
    )


@pytest.mark.parametrize("alias", ["staticmethod", "classmethod"])
def test_python_bound_self_rejects_aliased_builtin_descriptors(alias):
    adapter = python.PythonResolution()
    call = node("call", start=50, end=60)
    method = node(
        "function_definition",
        parameters=node("parameters", children=[node(value="self")]),
        body=node("block", children=[call]),
        start=10,
        end=90,
    )
    decorated = node(
        "decorated_definition", children=[node("decorator", "@descriptor"), method]
    )
    node("class_definition", body=node("block", children=[decorated]))
    imported = node(
        "import_from_statement",
        module_name=node(value="builtins"),
        name=[
            node(
                "aliased_import", name=node(value=alias), alias=node(value="descriptor")
            )
        ],
    )
    state = syntax(adapter=adapter, nodes=[imported], declarations={(50, 60): call})
    identity = SimpleNamespace(syntax={"src/main.py": state})
    assert adapter.select(identity, request(qualifier="self"), [symbol()]) == []


@pytest.mark.parametrize("shape", ["named", "fallback", "empty"])
def test_assignment_target_falls_back_only_when_named_field_is_missing(shape):
    adapter = python.PythonResolution()
    scope, target = node("block"), node(value="local")
    expression = (
        node("assignment", left=target)
        if shape == "named"
        else node("assignment", children=[target] if shape == "fallback" else [])
    )
    assert adapter.binding(syntax(), expression, scope) == (
        target if shape != "empty" else None,
        scope,
    )
