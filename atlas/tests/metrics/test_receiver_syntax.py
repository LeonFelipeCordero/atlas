"""Receiver declaration normalization without native parsing."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from atlas.metrics import receiver_syntax as module
from atlas.metrics.receiver_syntax import Declaration, ReceiverBinding
from tests.metrics.resolution_support import node


@pytest.fixture
def syntax():
    scope = node("function_definition", end=200)
    return SimpleNamespace(scope=Mock(return_value=scope), nodes=[], adapter=SimpleNamespace(
        receiver_class_nodes={"call"}, call_target=lambda n: (n.child_by_field_name("function"), None),
        assignments={"assignment"}, receiver_bindings=Mock(return_value=[])))


@pytest.mark.parametrize(("kind", "value", "expected"), [
    ("type_identifier", "pkg.Type", "pkg.Type"), ("type_identifier", "pkg::Type", "pkg::Type"),
    ("user_type", "Box<Item>", "Box"), ("type_identifier", "A | B", None),
    ("type_identifier", "T[]", None), ("type_identifier", "", None),
])
def test_type_name_accepts_only_supported_nominal_spelling(kind, value, expected):
    assert module.type_name(node(kind, value)) == expected


def test_type_name_unwraps_generic_reference_and_ignores_lifetime():
    generic = node("generic_type", name=node("type_identifier", "Box"))
    wrapped = node("reference_type", children=[node("lifetime", "'a"), generic])

    assert module.type_name(wrapped) == "Box"
    assert module.type_name(node("type_annotation", children=[generic, node("type_identifier", "Other")])) is None
    assert module.type_name(None) is None


@pytest.mark.parametrize("annotation", [None, "var"])
def test_declaration_infers_constructor_for_missing_or_var_annotation(syntax, annotation):
    name = node(value="receiver")
    value = node("call", function=node(value="Service"))
    declaration = node("variable_declarator", name=name, children=[name, value])

    result = module.declaration(syntax, declaration, Declaration(name, annotation, value))

    assert result == [ReceiverBinding("receiver", "Service", syntax.scope.return_value, declaration, True)]


def test_declared_annotation_wins_over_initializer(syntax):
    name = node(value="receiver")
    declaration = node("variable_declarator", name=name)

    assert module.declaration(syntax, declaration, Declaration(name, "Service")) == [
        ReceiverBinding("receiver", "Service", syntax.scope.return_value, declaration)]


def test_missing_name_or_member_scope_produces_no_binding(syntax):
    declaration = node("field_declaration")

    assert module.declaration(syntax, declaration, Declaration(None, "Service")) == []
    assert module.declaration(syntax, declaration, Declaration(node(value="x"), "Service", member=True)) == []


def test_java_field_uses_class_scope_and_static_modifier(syntax):
    declaration = node("variable_declarator", name=node(value="service"))
    field = node("field_declaration", children=[node("modifiers", "private static"), declaration],
                 type=node("type_identifier", "Service"))
    owner = node("class_declaration", children=[field])

    assert module.java_bindings(syntax, declaration) == [
        ReceiverBinding("service", "Service", owner, declaration, member=True, static=True)]


@pytest.mark.parametrize(("object_name", "expected"), [("self", "service"), ("other", None)])
def test_python_member_assignment_requires_self(syntax, object_name, expected):
    target = node("attribute", object=node(value=object_name), attribute=node(value="service"))
    declaration = node("assignment", left=target, type=node("type_identifier", "Service"))
    node("class_definition", children=[declaration])

    bindings = module.python_bindings(syntax, declaration)

    assert [binding.name for binding in bindings] == ([expected] if expected else [])


def test_member_constructor_inference_is_rejected_outside_constructor(syntax):
    target = node("attribute", object=node(value="self"), attribute=node(value="service"))
    declaration = node("assignment", left=target, right=node("call", function=node(value="Service")))
    method = node("function_definition", name=node(value="reset"), body=declaration)
    node("class_definition", children=[method])

    result = module.python_bindings(syntax, declaration)

    assert [(binding.annotation, binding.inferred, binding.member) for binding in result] == [(None, True, True)]


@pytest.mark.parametrize(("count", "expected"), [(1, [None, None]), (2, ["First", "Second"])])
def test_go_short_declaration_pairs_only_one_value_per_name(syntax, count, expected):
    values = [node("call", function=node(value=name)) for name in ["First", "Second"][:count]]
    declaration = node("short_var_declaration",
                       left=node("expression_list", children=[node(value="a"), node(value="b")]),
                       right=node("expression_list", children=values))

    bindings = module.go_bindings(syntax, declaration)

    assert [(b.name, b.annotation) for b in bindings] == list(zip(["a", "b"], expected))


def test_rust_destructured_let_is_not_a_nominal_receiver(syntax):
    declaration = node("let_declaration", pattern=node("tuple_pattern", children=[node(value="a")]),
                       type=node("type_identifier", "Service"))

    assert module.rust_bindings(syntax, declaration) == []


def test_kotlin_constructor_parameter_requires_property_keyword(syntax):
    parameter = node("class_parameter", children=[node("simple_identifier", "service"), node("user_type", "Service")])

    assert module.kotlin_bindings(syntax, parameter) == []


@pytest.mark.parametrize(("language", "kind", "name_field"), [
    ("java", "formal_parameter", "name"), ("kotlin", "parameter", "children"),
    ("python", "typed_parameter", "children"), ("script", "required_parameter", "name"),
    ("script", "optional_parameter", "pattern"), ("go", "parameter_declaration", "name"),
    ("rust", "parameter", "pattern"), ("rust", "let_declaration", "pattern"),
])
def test_typed_parameters_and_locals_keep_nominal_type_and_lexical_scope(syntax, language, kind, name_field):
    name, annotation = node("simple_identifier" if language == "kotlin" else "identifier", "service"), node("user_type" if language == "kotlin" else "type_identifier", "Service")
    fields = {"type": annotation}
    if name_field == "children":
        fields["children"] = [name, annotation]
    else:
        fields[name_field] = name
    declaration = node(kind, **fields)

    bindings = getattr(module, language + "_bindings")(syntax, declaration)

    assert bindings == [ReceiverBinding("service", "Service", syntax.scope.return_value, declaration)]


@pytest.mark.parametrize(("language", "kind", "owner_kind"), [
    ("kotlin", "class_parameter", "class_declaration"),
    ("kotlin", "variable_declaration", "class_declaration"),
    ("python", "assignment", "class_definition"),
    ("script", "public_field_definition", "class_declaration"),
    ("script", "required_parameter", "class_declaration"),
    ("go", "field_declaration", "type_spec"),
    ("rust", "field_declaration", "struct_item"),
])
def test_class_fields_use_class_scope_instead_of_method_scope(syntax, language, kind, owner_kind):
    name = node("simple_identifier" if language == "kotlin" else "identifier", "service")
    annotation = node("user_type" if language == "kotlin" else "type_identifier", "Service")
    declaration = node(kind, name=name, type=annotation, left=name)
    if language == "kotlin":
        declaration.children = declaration.named_children = [name, annotation, node("val")]
    if language == "script" and kind == "required_parameter":
        declaration.named_children.append(node("accessibility_modifier", "public"))
    if language == "kotlin" and kind == "variable_declaration":
        prop = node("property_declaration", children=[declaration])
        body = node("class_body", children=[prop])
        owner = node(owner_kind, children=[body])
    else:
        owner = node(owner_kind, children=[declaration])
    if language == "python":
        syntax.scope.return_value = owner

    bindings = getattr(module, language + "_bindings")(syntax, declaration)

    assert bindings == [ReceiverBinding("service", "Service", owner, declaration, member=True)]


@pytest.mark.parametrize("case", ["known", "written", "ambiguous", "no_parameters", "no_method"])
def test_constructor_field_inference_uses_unique_unchanged_injected_parameter(syntax, case):
    parameter = node("typed_parameter", start=1, end=5)
    parameters = node("parameters", children=[parameter])
    target = node("attribute", object=node(value="self"), attribute=node(value="service"))
    assignment = node("assignment", start=10, end=20, left=target, right=node(value="dependency"))
    method = node("function_definition", name=node(value="__init__"), body=assignment,
                  **({} if case == "no_parameters" else {"parameters": parameters}))
    owner = node("class_definition", children=[assignment if case == "no_method" else method])
    binding = ReceiverBinding("dependency", "Service", method, parameter)
    syntax.adapter.receiver_bindings.return_value = [binding, binding] if case == "ambiguous" else [binding]
    if case == "written":
        syntax.nodes = [node("assignment", start=30, end=40, left=node(value="dependency"))]

    result = module.python_bindings(syntax, assignment)

    assert result == [ReceiverBinding("service", "Service" if case == "known" else None, owner, assignment, inferred=True, member=True)]


def test_script_this_constructor_assignment_infers_member_type(syntax):
    target = node("member_expression", object=node(value="this"), property=node(value="service"))
    assignment = node("assignment_expression", left=target, right=node("call", function=node(value="Service")))
    method = node("method_definition", name=node(value="constructor"), body=assignment)
    owner = node("class_declaration", children=[method])

    assert module.script_bindings(syntax, assignment) == [
        ReceiverBinding("service", "Service", owner, assignment, inferred=True, member=True)]


def test_script_ignores_assignment_to_another_objects_member(syntax):
    assignment = node("assignment_expression", left=node("member_expression", object=node(value="other"), property=node(value="service")))

    assert module.script_bindings(syntax, assignment) == []
