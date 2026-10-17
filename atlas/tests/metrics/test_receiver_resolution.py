"""Receiver policy preserves unknown versus rejected types and lexical safety."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from atlas.metrics.receiver_resolution import ReceiverTypes
from atlas.metrics.receiver_syntax import ReceiverBinding
from atlas.metrics.resolution_contract import ResolutionRequest
from tests.metrics.resolution_support import call, node, parsed_file, symbol


@pytest.fixture
def context():
    file = parsed_file()
    request = ResolutionRequest(file, call(), None, "run", "service")
    adapter = SimpleNamespace(self_qualifiers={"self"}, bare_instance_fields=False,
                              trust_receiver_annotations=True, assignments={"assignment"},
                              receiver_updates={"update"}, declarations={"declaration"},
                              member_writes={"assignment"}, receiver_type_allowed=Mock(return_value=True),
                              qualify_class=lambda resolver, request, types: types,
                              validate_receiver_initializer=False, write_target=lambda n: n.child_by_field_name("left"))
    syntax = SimpleNamespace(file=file, adapter=adapter, nodes=[], bindings=[],
                             _visible=lambda scope, pos: scope.start_byte <= pos < scope.end_byte)
    resolver = SimpleNamespace(syntax={"a.py": syntax}, members=Mock(side_effect=lambda types, name, static: [symbol()] if types else []),
                               named=Mock(return_value=[symbol(kind="class")]), owner=Mock(return_value=None))
    receivers = ReceiverTypes(resolver)
    receivers.bindings = {"a.py": []}
    return receivers, syntax, request


@pytest.mark.parametrize(("types", "expected"), [(None, None), ([], []), ([symbol(kind="class")], ["target"])])
def test_resolve_distinguishes_unknown_from_known_receiver(context, monkeypatch, types, expected):
    receivers, _, request = context
    monkeypatch.setattr(receivers, "_receiver_types", Mock(return_value=types))

    result = receivers.resolve(request)

    assert (None if result is None else [s.key for s in result]) == expected
    if types is None:
        receivers.resolver.members.assert_not_called()
    else:
        receivers.resolver.members.assert_called_once_with(types, "run", False)


def test_nearest_binding_prefers_declared_type_only_within_smallest_scope(context):
    receivers, _, _ = context
    outer, inner = node("block", end=100), node("block", start=10, end=30)
    inferred = ReceiverBinding("service", "Inferred", inner, node(), inferred=True)
    declared = replace(inferred, annotation="Declared", inferred=False)
    distant = replace(declared, scope=outer)

    assert receivers._nearest([distant, inferred, declared]) == [declared]


@pytest.mark.parametrize(("position", "member", "expected"), [(0, False, True), (99, False, True), (100, False, False), (20, True, False)])
def test_candidate_visibility_has_half_open_bounds_and_rejects_bare_fields(context, position, member, expected):
    receivers, syntax, request = context
    binding = ReceiverBinding("service", "Service", node("block"), node(), member=member)

    assert receivers._visible(syntax, binding, replace(request, call=call(start=position))) is expected


@pytest.mark.parametrize(("start", "annotation", "expected"), [(19, "Service", False), (20, "Service", True), (21, "Service", True), (19, None, True)])
def test_unsafe_rejects_use_before_declaration_and_missing_annotation(context, start, annotation, expected):
    receivers, syntax, request = context
    binding = ReceiverBinding("service", annotation, node("block"), node(start=start))

    assert receivers._unsafe(syntax, binding, request) is expected


@pytest.mark.parametrize(("inferred", "trusted", "expected"), [(False, True, False), (True, True, True), (False, False, True)])
def test_conditional_declarations_require_trusted_explicit_annotation(context, inferred, trusted, expected):
    receivers, syntax, _ = context
    declaration = node("declaration")
    branch = node("if_statement", children=[declaration])
    scope = node("block", children=[branch])
    syntax.adapter.trust_receiver_annotations = trusted
    binding = ReceiverBinding("service", "Service", scope, declaration, inferred=inferred)

    assert receivers._conditional(syntax, binding) is expected


@pytest.mark.parametrize(("kinds", "expected"), [(["class", "impl"], ["0"]), (["function"], None), (["trait", "struct"], ["0", "1"])])
def test_type_symbols_rejects_non_type_identity_and_discards_impl(context, kinds, expected):
    receivers, _, _ = context

    result = receivers._type_symbols([symbol(key=str(i), kind=kind) for i, kind in enumerate(kinds)])

    assert (None if result is None else [s.key for s in result]) == expected


@pytest.mark.parametrize(("left", "right", "expected"), [
    ([symbol()], [symbol()], False), ([symbol()], [symbol(key="other")], True),
    ([], [], True), ([symbol(), symbol(key="other")], [symbol()], True),
])
def test_initializer_requires_single_matching_identity(context, left, right, expected):
    receivers, _, _ = context

    assert receivers._conflicting_types(left, right) is expected


def test_declared_type_lookup_uses_declaration_context_not_call_site(context, monkeypatch):
    receivers, syntax, request = context
    binding = ReceiverBinding("service", "Service", node("block"), node(start=4, end=9))
    monkeypatch.setattr(receivers, "_identity_overwritten", Mock(return_value=False))

    result = receivers._declared_types(syntax, binding, request)

    assert result == [symbol(kind="class")]
    receivers.resolver.named.assert_called_once_with(ResolutionRequest(
        syntax.file, replace(request.call, start_byte=4, end_byte=9), None, "Service", None))


@pytest.mark.parametrize("initialized", [[], [symbol(key="different", kind="class")]])
def test_declared_type_rejects_initializer_identity_conflict(context, monkeypatch, initialized):
    receivers, syntax, request = context
    binding = ReceiverBinding("service", "Service", node("block"), node(start=4, end=9))
    monkeypatch.setattr(receivers, "_initializer_types", Mock(return_value=initialized))

    assert receivers._declared_types(syntax, binding, request) == []


@pytest.mark.parametrize(("types", "expected"), [(None, None), ([], []), ([symbol(), symbol(key="other")], [])])
def test_fields_preserves_unknown_and_rejects_ambiguous_owner(context, types, expected):
    receivers, _, request = context

    assert receivers._fields(types, "client", request) == expected


def test_binding_types_rejects_ambiguity_without_guessing(context):
    receivers, syntax, request = context
    binding = ReceiverBinding("service", "Service", node("block"), node())

    assert receivers._binding_types(syntax, [binding, replace(binding, annotation="Other")], request) == []
    receivers.resolver.named.assert_not_called()


@pytest.mark.parametrize(("paths", "left", "right", "expected"), [
    ({"service.client"}, "alias", "service", {"alias.client"}),
    ({"alias.client"}, "alias", "service", {"service.client"}),
    ({"services.client"}, "alias", "service", set()),
])
def test_aliases_preserve_suffix_and_require_path_component_boundary(context, paths, left, right, expected):
    receivers, _, _ = context

    assert receivers._alias_paths(paths, left, right) == expected


def test_alias_expansion_reaches_fixed_point_across_reverse_order_chain(context):
    receivers, syntax, _ = context
    declarations = [node("declaration", left=node(value="second"), right=node(value="first")),
                    node("declaration", left=node(value="first"), right=node(value="service"))]

    assert receivers._expand_paths(syntax, declarations, {"service.client"}) == {
        "service.client", "first.client", "second.client"}


def test_missing_call_node_is_unsafe_for_receiver_writes(context):
    receivers, syntax, request = context
    syntax.node = Mock(return_value=None)

    assert receivers._path_written(request) is True


@pytest.mark.parametrize(("receiver", "target", "expected"), [
    (True, "service", True), (False, "service", False), (False, "service.run", True),
    (True, "service.runner", False),
])
def test_path_writes_distinguishes_receiver_from_called_member(context, receiver, target, expected):
    receivers, syntax, request = context
    site = node("call", start=20, end=25)
    write = node("assignment", left=node("attribute", target), start=30, end=40)
    scope = node("function_definition", children=[site, write])
    syntax.nodes = [scope, site, write]
    syntax.node = Mock(return_value=site)

    assert receivers._path_written(request, receiver=receiver) is expected


def test_reassigned_ignores_original_binding_and_out_of_scope_write(context):
    receivers, syntax, _ = context
    declaration = node("assignment", left=node(value="service"), start=5, end=10)
    outside = node("assignment", left=node(value="service"), start=100, end=110)
    binding = ReceiverBinding("service", "Service", node("block", end=100), declaration)
    syntax.nodes = [declaration, outside]

    assert receivers._reassigned(syntax, binding, "service") is False
    syntax.nodes.append(node("update", left=node(value="service"), start=99, end=100))
    assert receivers._reassigned(syntax, binding, "service") is True
