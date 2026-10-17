"""Syntax extraction and lexical binding policies without a parser."""

from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import go, java, javascript, kotlin, python, rust
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from atlas.metrics.resolution_contract import DeclarationLookup
from tests.metrics.adapter_support import node, request, symbol, syntax


@pytest.mark.parametrize(
    "case",
    [
        (ResolutionAdapter(), "call", {"function": "run"}, ("run", None)),
        (
            ResolutionAdapter(),
            "call",
            {"receiver": "obj", "method": "run"},
            ("run", "obj"),
        ),
        (
            python.PythonResolution(),
            "attribute",
            {"object": "obj", "attribute": "run"},
            ("run", "obj"),
        ),
        (
            javascript.JavaScriptResolution(),
            "member_expression",
            {"object": "obj", "property": "run"},
            ("run", "obj"),
        ),
        (
            go.GoResolution(),
            "selector_expression",
            {"operand": "obj", "field": "Run"},
            ("Run", "obj"),
        ),
        (go.GoResolution(), "composite_literal", {"type": "Widget"}, ("Widget", None)),
        (
            rust.RustResolution(),
            "struct_expression",
            {"name": "Widget"},
            ("Widget", None),
        ),
        (
            java.JavaResolution(),
            "object_creation_expression",
            {"type": "Widget"},
            ("Widget", None),
        ),
        (
            javascript.JavaScriptResolution(),
            "new_expression",
            {"constructor": "Widget"},
            ("Widget", None),
        ),
    ],
)
def test_call_target_extracts_language_fields(case):
    adapter, kind, fields, expected = case
    # Given a syntax node with language-specific fields, when normalized, then names survive.
    expression = node(kind, **{key: node(value=value) for key, value in fields.items()})
    callee, receiver = adapter.call_target(expression)
    result = adapter.normalized_call(request().call, callee, receiver)
    assert (result.name, result.qualifier) == expected


@pytest.mark.parametrize("operator", ["&", "*", "-"])
@pytest.mark.parametrize("literal", [True, False])
def test_go_address_of_only_accepts_composite_literals(operator, literal):
    target = node(value="Widget")
    operand = node("composite_literal" if literal else "identifier", type=target)
    expression = node(
        "unary_expression", operator=node(value=operator), operand=operand
    )
    assert go.GoResolution().call_target(expression) == (
        (target, None) if operator == "&" and literal else (None, None)
    )


def test_method_reference_and_kotlin_navigation_extract_receiver():
    receiver, member = node(value="obj"), node(value="run")
    reference = node("method_reference", children=[receiver, member])
    navigation = node(
        "navigation_expression",
        children=[receiver, node("navigation_suffix", children=[member])],
    )
    call = node("call_expression", function=navigation)
    assert java.JavaResolution().call_target(reference) == (member, receiver)
    assert kotlin.KotlinResolution().call_target(call) == (member, receiver)


@pytest.mark.parametrize(
    "case",
    [
        (python.PythonResolution(), "function_definition", "name", False),
        (python.PythonResolution(), "class_definition", "name", False),
        (python.PythonResolution(), "except_clause", "alias", False),
        (python.PythonResolution(), "as_pattern", "parameter", False),
        (javascript.JavaScriptResolution(), "function_declaration", "name", False),
        (javascript.JavaScriptResolution(), "function_expression", "name", True),
        (java.JavaResolution(), "enhanced_for_statement", "name", True),
        (java.JavaResolution(), "catch_formal_parameter", "name", False),
        (ResolutionAdapter(), "assignment", "left", False),
        (ResolutionAdapter(), "declaration", "pattern", False),
        (ResolutionAdapter(), "loop", "left", False),
    ],
)
def test_bindings_keep_target_and_correct_scope(case):
    adapter, kind, field_name, own_scope = case
    adapter.assignments = adapter.assignments | {"assignment"}
    adapter.declarations = adapter.declarations | {"declaration"}
    adapter.loop_bindings = adapter.loop_bindings | {"loop"}
    scope, target = node("block"), node(value="local")
    declaration = node(kind, **{field_name: target})
    assert adapter.binding(syntax(), declaration, scope) == (
        target,
        declaration if own_scope else scope,
    )


@pytest.mark.parametrize("kind", ["property_declaration", "for_statement"])
@pytest.mark.parametrize("present", [True, False])
def test_kotlin_binding_searches_declarations_not_expression_children(kind, present):
    scope, target = node("block"), node("variable_declaration", "item")
    declaration = node(
        kind, children=[node("expression"), *([target] if present else [])]
    )
    assert kotlin.KotlinResolution().binding(syntax(), declaration, scope) == (
        target if present else None,
        declaration if kind == "for_statement" else scope,
    )


@pytest.mark.parametrize("declares", [True, False])
def test_go_range_assignment_does_not_create_loop_local(declares):
    outer, loop, target = node("block"), node("for_statement"), node(value="item")
    clause = node(
        "range_clause", left=target, children=[node(":=" if declares else "=")]
    )
    loop.children.append(clause)
    clause.parent = loop
    assert go.GoResolution().binding(syntax(scope=lambda n: outer), clause, loop) == (
        target,
        loop if declares else outer,
    )


@pytest.mark.parametrize("keyword", ["var", "let"])
def test_script_var_hoists_to_function_but_let_stays_in_block(keyword):
    function = node("function_declaration")
    inner = node("statement_block")
    inner.parent = function
    target = node(value="item")
    declaration = node("variable_declarator", name=target)
    node("variable_declaration", f"{keyword} item", children=[declaration])
    assert javascript.JavaScriptResolution().binding(
        syntax(scope=lambda n: function), declaration, inner
    ) == (target, function if keyword == "var" else inner)


def test_python_walrus_escapes_nested_comprehension_scopes():
    outer = node("function_definition")
    inner = node("list_comprehension")
    middle = node("generator_expression")
    target = node(value="item")
    parents = {inner: middle, middle: outer}
    assert python.PythonResolution().binding(
        syntax(scope=lambda n: parents[n]), node("named_expression", name=target), inner
    ) == (target, outer)


@pytest.mark.parametrize("position", [19, 20, 29, 30])
def test_python_comprehension_target_is_not_visible_in_its_iterable(position):
    comprehension = node(
        "list_comprehension",
        children=[node("for_in_clause", right=node(start=20, end=30))],
    )
    assert python.PythonResolution().visible(syntax(), comprehension, position) is (
        not 20 <= position < 30
    )


@pytest.mark.parametrize(
    "nested",
    ["none", "function_definition", "lambda", "class_definition", "list_comprehension"],
)
@pytest.mark.parametrize("position", [9, 20, 90])
def test_python_class_visibility_excludes_nested_bodies(nested, position):
    body = node("block", start=10, end=90)
    owner = node("class_definition", body=body)
    leaf = node(start=position, end=position + 1)
    if nested == "none":
        leaf.parent = body
    else:
        nested_body = node("block", start=15, end=80, children=[leaf])
        child = node(nested, body=nested_body)
        child.parent = body
    root = node("module")
    root.descendant_for_byte_range = lambda start, end: leaf
    assert python.PythonResolution().visible(syntax(root=root), owner, position) is (
        10 <= position < 90 and nested == "none"
    )


@pytest.mark.parametrize("visible", [True, False])
def test_python_import_blocks_class_declaration_only_when_visible(visible):
    scope = node("function_definition")
    lookup = DeclarationLookup("Widget", node("class_definition"), 50)
    state = syntax(
        imports=[("Widget", scope)], _visible=lambda scope, position: visible
    )
    assert python.PythonResolution().declaration_allowed(state, lookup) is (not visible)


@pytest.mark.parametrize("position", [9, 10, 89, 90])
def test_python_hidden_class_import_shadowing_respects_body_boundary(position):
    owner = node("class_definition", body=node("block", start=10, end=90))
    state = syntax(imports=[("Widget", owner)], _visible=lambda scope, position: False)
    assert python.PythonResolution().import_shadowed(state, "Widget", position) is (
        10 <= position < 90
    )


@pytest.mark.parametrize("decorator", ["@staticmethod", "@classmethod", "@wrapper"])
def test_python_static_dispatch_recognizes_only_builtin_method_decorators(decorator):
    method = symbol()
    declaration = node("function_definition")
    node("decorated_definition", children=[node("decorator", decorator), declaration])
    state = syntax(declarations={(method.start_byte, method.end_byte): declaration})
    assert python.PythonResolution().static(state, method) is (decorator != "@wrapper")


@pytest.mark.parametrize("has_self", [True, False])
@pytest.mark.parametrize("rebound", [True, False])
def test_python_implicit_receiver_requires_self_parameter_without_rebinding(
    has_self, rebound
):
    method = symbol()
    parameters = node(
        "parameters", children=[node(value="self" if has_self else "other")]
    )
    declaration = node("function_definition", parameters=parameters)
    state = syntax(
        declarations={(10, 20): declaration},
        bindings=[
            (
                "self",
                node("block", start=0, end=100),
                node("assignment") if rebound else parameters,
            )
        ],
    )
    resolver = SimpleNamespace(syntax={method.file_path: state})
    assert python.PythonResolution().implicit_receiver(
        resolver, request(qualifier="self"), method
    ) is (has_self and not rebound)


@pytest.mark.parametrize("kind", ["arrow_function", "function_expression", "missing"])
def test_script_implicit_this_survives_only_arrow_closures(kind):
    method, closure = symbol("method"), symbol("closure", start=30, end=40)
    state = syntax(declarations={(30, 40): node(kind)} if kind != "missing" else {})
    resolver = SimpleNamespace(
        syntax={method.file_path: state}, ancestors=lambda owner: [closure, method]
    )
    assert javascript.JavaScriptResolution().implicit_receiver(
        resolver, request(qualifier="this"), method
    ) is (kind == "arrow_function")
