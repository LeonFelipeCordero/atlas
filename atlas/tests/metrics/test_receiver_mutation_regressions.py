"""Receiver safety boundaries missed by the completed mutation campaign."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from atlas.metrics.receiver_syntax import ReceiverBinding
from tests.metrics.resolution_support import call, node, symbol
from tests.metrics.test_receiver_bindings import indexed as indexed
from tests.metrics.test_receiver_resolution import context as context


@pytest.mark.parametrize("qualifier", ["", "pkg.Type", "pkg::Type"])
def test_lexical_receiver_rejects_nonlexical_spellings(indexed, qualifier):
    receivers, syntax, request, _ = indexed
    receivers._candidates = Mock(side_effect=AssertionError("not a lexical receiver"))

    assert receivers._lexical_types(request, qualifier, syntax) is None


@pytest.mark.parametrize(("qualifier", "expected"), [
    ("service", False), ("self", False), ("other.service", False), ("self.service", True),
])
def test_member_receiver_requires_both_path_and_implicit_root(indexed, qualifier, expected):
    receivers, syntax, request, _ = indexed

    assert receivers._member_receiver(syntax, replace(request, qualifier=qualifier)) is expected


@pytest.mark.parametrize("case", [
    (9, True, False), (10, True, True), (19, True, True), (20, True, False), (15, False, False),
])
def test_explicit_member_visibility_is_half_open(indexed, case):
    position, member, expected = case
    receivers, syntax, request, _ = indexed
    binding = ReceiverBinding("service", "Service", node("class_definition", start=10, end=20), node(), member=member)

    assert receivers._visible(syntax, binding, replace(request, qualifier="self.service", call=call(start=position))) is expected


@pytest.mark.parametrize(("start", "expected"), [(10, True), (19, True), (20, False)])
def test_field_binding_span_is_half_open_and_requires_direct_owner(context, start, expected):
    receivers, _, _ = context
    owner = symbol(kind="class", start=10, end=20)
    scope = node("class_definition", start=10, end=20)
    binding = ReceiverBinding("client", "Client", scope, node(start=start, end=start + 1), member=True)
    receivers.bindings["a.py"] = [binding, replace(binding, scope=node("class_definition", start=12, end=18))]

    assert receivers._field_bindings(owner, "client") == ([binding] if expected else [])


@pytest.mark.parametrize(("start", "expected"), [(10, True), (19, True), (20, False)])
def test_constructor_parameter_selection_obeys_half_open_bounds(context, start, expected):
    receivers, syntax, _ = context
    binding = ReceiverBinding("client", "Client", node("class_definition"), node(), member=True)
    parameter = ReceiverBinding("dependency", "Client", node("block"), node(start=start, end=start + 1))
    receivers.bindings["a.py"] = [parameter]
    write = node("assignment", right=node(value="dependency"))

    assert receivers._constructor_initialization(syntax, binding, (node("constructor_declaration", start=10, end=20), write)) is expected


@pytest.mark.parametrize("case", [
    ("class", True, False), ("method", False, False), ("function", True, True),
])
def test_static_context_requires_a_static_callable_ancestor(indexed, case):
    kind, static, expected = case
    receivers, syntax, request, _ = indexed
    receivers.resolver.ancestors.return_value = [symbol(kind=kind)]
    syntax.static.return_value = static

    assert receivers._static(request) is expected


@pytest.mark.parametrize("case", [
    (10, 30, 10, True), (10, 30, 30, False), (10, 110, 20, False), (15, 25, 20, True),
])
def test_shadowing_compares_scope_widths_and_half_open_bounds(context, case):
    start, end, position, expected = case
    receivers, syntax, _ = context
    binding = ReceiverBinding("service", "Service", node("block", start=0, end=80), node(start=5, end=8))
    syntax.bindings = [("service", node("block", start=start, end=end), node("parameter", start=1, end=3))]

    assert receivers._shadowed(syntax, binding, position) is expected


@pytest.mark.parametrize("case", [(120, 180, True), (0, 250, False)])
def test_shadowing_uses_width_not_endpoint_sum_for_nonzero_scope(context, case):
    start, end, expected = case
    receivers, syntax, _ = context
    binding = ReceiverBinding(
        "service", "Service", node("block", start=100, end=200), node(start=110, end=115)
    )
    syntax.bindings = [
        ("service", node("block", start=start, end=end), node("parameter", start=101, end=105))
    ]

    assert receivers._shadowed(syntax, binding, 150) is expected


def test_shadow_declaration_ending_at_receiver_is_not_its_container(context):
    receivers, syntax, _ = context
    scope = node("block")
    binding = ReceiverBinding("service", "Service", scope, node(start=10, end=15))
    syntax.bindings = [("service", scope, node("parameter", start=1, end=10))]

    assert receivers._shadowed(syntax, binding, 20) is True


@pytest.mark.parametrize("case", [(True, True, True), (False, False, True), (False, True, False)])
def test_constructor_initialization_requires_explicit_trusted_member(context, case):
    inferred, member, trusted = case
    receivers, syntax, _ = context
    write = node("assignment")
    node("constructor_declaration", children=[write])
    binding = ReceiverBinding("service", "Service", node("class_declaration"), node(), inferred, member)
    syntax.adapter.trust_receiver_annotations = trusted
    receivers._constructor_initialization = Mock(return_value=True)

    assert receivers._field_initialization(syntax, binding, write) is False
    receivers._constructor_initialization.assert_not_called()


@pytest.mark.parametrize(("start", "expected"), [(0, True), (99, True), (100, False)])
def test_reassignment_includes_scope_start_but_not_end(context, start, expected):
    receivers, syntax, _ = context
    binding = ReceiverBinding("service", "Service", node("block"), node(start=5, end=8))
    syntax.nodes = [node("assignment", start=start, end=start + 1, left=node(value="service"))]

    assert receivers._reassigned(syntax, binding, "service") is expected


@pytest.mark.parametrize("target", [None, node("attribute", "other.service")])
def test_alias_requires_simple_target_even_with_nonempty_value(context, target):
    receivers, _, _ = context
    fields = {"right": node(value="service")}
    if target is not None:
        fields["left"] = target

    assert receivers._node_aliases(node("assignment", **fields), {"service"}) == set()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_go_expression_list_unwraps_exactly_one_expression(context, count):
    receivers, _, _ = context
    children = [node(value=str(i)) for i in range(count)]
    expression = node("expression_list", children=children)

    assert receivers._single_expression(expression) is (children[0] if count == 1 else expression)
    identifier = node(value="service")
    assert receivers._single_expression(identifier) is identifier
    assert receivers._single_expression(None) is None


def test_unknown_implicit_owner_falls_back_to_lexical_binding(indexed):
    receivers, _, request, scope = indexed
    receivers.bindings["a.py"] = [ReceiverBinding("self", "Service", scope, node(start=1, end=5))]

    assert receivers._receiver_types(replace(request, qualifier="self")) == [symbol(kind="class")]


@pytest.mark.parametrize(("start", "expected"), [(0, True), (99, True), (100, False)])
def test_path_write_scan_obeys_function_boundaries(indexed, start, expected):
    receivers, syntax, request, scope = indexed
    scope.start_byte, scope.end_byte = 0, 100
    syntax.nodes.append(node("assignment", start=start, end=start + 1, left=node("attribute", "service.run")))

    assert receivers._path_written(request) is expected
