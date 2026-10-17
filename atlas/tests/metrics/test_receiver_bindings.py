"""Receiver binding, field and identity scenarios on synthetic syntax indexes."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from atlas.metrics.receiver_syntax import ReceiverBinding
from tests.metrics.resolution_support import node, symbol
from tests.metrics.test_receiver_resolution import context as context


@pytest.fixture
def indexed(context):
    receivers, syntax, request = context
    site = node("call", start=20, end=25)
    scope = node("function_definition", children=[site])
    syntax.node = Mock(return_value=site)
    syntax.nodes = [scope, site]
    syntax.adapter.receiver_class_nodes = {"new"}
    syntax.adapter.call_target = lambda n: (n.child_by_field_name("function"), n.child_by_field_name("receiver"))
    syntax.adapter.receiver_owner = Mock(return_value=None)
    syntax.static = Mock(return_value=False)
    receivers.resolver._self_class = Mock(return_value=[symbol(kind="class")])
    receivers.resolver.ancestors = Mock(return_value=[])
    receivers.resolver.qualified = Mock(return_value=[])
    receivers.resolver.members.side_effect = lambda types, name, static: [symbol()] if len(types) == 1 else []
    return receivers, syntax, request, scope


def test_receiver_index_collects_all_bindings_once_per_file(context):
    receivers, syntax, _ = context
    declaration = node("declaration")
    binding = ReceiverBinding("service", "Service", node("block"), declaration)
    syntax.nodes = [node("comment"), declaration]
    syntax.adapter.receiver_bindings = Mock(side_effect=lambda syntax, n: [binding] if n is declaration else [])
    del receivers.bindings

    first = receivers.bindings
    syntax.nodes.clear()

    assert (first, receivers.bindings) == ({"a.py": [binding]}, {"a.py": [binding]})
    assert syntax.adapter.receiver_bindings.call_count == 2


@pytest.mark.parametrize("case", ["known", "missing", "ambiguous", "future", "shadowed", "reassigned", "member_write", "unrelated"])
def test_lexical_receiver_resolution_rejects_unsafe_or_ambiguous_bindings(indexed, case):
    receivers, syntax, request, scope = indexed
    declaration = node("declaration", start=21 if case == "future" else 2, end=8)
    binding = ReceiverBinding("service", "Service", scope, declaration)
    receivers.bindings["a.py"] = [] if case == "missing" else [binding]
    if case == "known":
        receivers.bindings["a.py"].append(replace(binding, name="other", annotation="Other"))
    if case == "ambiguous":
        receivers.bindings["a.py"].append(replace(binding, annotation="Other"))
    if case == "shadowed":
        syntax.bindings = [("service", scope, node("parameter", start=0, end=1))]
    if case in {"reassigned", "member_write", "unrelated"}:
        target = {"reassigned": "service", "member_write": "service.run", "unrelated": "other.stop"}[case]
        syntax.nodes.append(node("assignment", start=30, end=40, left=node("attribute", target)))

    result = receivers.resolve(request)

    assert result == (None if case == "missing" else [symbol()] if case in {"known", "unrelated"} else [])


@pytest.mark.parametrize("case", ["self", "field", "written", "unknown", "no_instance", "static", "bare_field"])
def test_implicit_and_member_receiver_resolution_respects_owner_and_static_context(indexed, case):
    receivers, syntax, request, scope = indexed
    owner = symbol(key="owner", kind="class")
    declaration = node("declaration", start=2, end=8)
    scope.type = "class_definition"
    binding = ReceiverBinding("service", "Service", scope, declaration, member=True)
    receivers.bindings["a.py"] = [binding]
    qualifier = "self" if case in {"self", "unknown", "written"} else "service" if case == "bare_field" else "self.service"
    request = replace(request, qualifier=qualifier)
    if case not in {"no_instance", "static", "bare_field"}:
        syntax.adapter.receiver_owner.return_value = None if case == "unknown" else [owner]
    if case == "written":
        syntax.nodes.append(node("assignment", start=30, left=node(value="self")))
    if case == "no_instance":
        receivers.resolver._self_class.return_value = []
    if case == "static":
        receivers.resolver.ancestors.return_value = [symbol(kind="method")]
        syntax.static.return_value = True

    result = receivers._receiver_types(request)

    assert result == ([owner] if case == "self" else [symbol(kind="class")] if case == "field" else None if case in {"unknown", "bare_field"} else [])


@pytest.mark.parametrize("case", ["known", "missing", "duplicate", "other_class", "conditional", "reassigned"])
def test_field_chain_requires_unique_unmodified_field_in_owner_span(indexed, case):
    receivers, syntax, request, scope = indexed
    owner = symbol(key="owner", kind="class", end=100)
    root = ReceiverBinding("service", "Service", scope, node("declaration", start=2, end=8))
    field_node = node("declaration", start=110 if case == "other_class" else 10, end=120 if case == "other_class" else 15)
    field = ReceiverBinding("client", "Client", scope, field_node, member=True, inferred=case == "conditional")
    if case == "conditional":
        node("if_statement", children=[field_node])
    receivers.bindings["a.py"] = [root] + ([] if case == "missing" else [field])
    if case == "duplicate":
        receivers.bindings["a.py"].append(replace(field, annotation="Other"))
    if case == "reassigned":
        syntax.nodes.append(node("assignment", start=30, end=40, left=node("attribute", "service.client")))
    receivers.resolver.named.side_effect = lambda request: [owner] if request.name == "Service" else [symbol(key="client_type", kind="class")]

    result = receivers._receiver_types(replace(request, qualifier="service.client"))

    assert result == ([symbol(key="client_type", kind="class")] if case == "known" else [])


@pytest.mark.parametrize("annotation", ["pkg.Service", "pkg::Service", "Service"])
def test_qualified_annotation_uses_qualified_lookup_only_when_local_type_missing(indexed, annotation):
    receivers, syntax, request, scope = indexed
    target = symbol(kind="class")
    receivers.resolver.named.return_value = []
    receivers.resolver.qualified.return_value = [target]
    binding = ReceiverBinding("service", annotation, scope, node(start=2, end=8))

    result = receivers._declared_types(syntax, binding, request)

    assert result == ([] if annotation == "Service" else [target])


@pytest.mark.parametrize("case", ["denied", "non_type", "qualified", "matching", "identifier", "unknown_value", "missing_value", "inferred"])
def test_initializer_validation_checks_identity_not_annotation_spelling(indexed, case):
    receivers, syntax, request, scope = indexed
    target = symbol(kind="class")
    syntax.adapter.validate_receiver_initializer = True
    syntax.adapter.receiver_type_allowed.return_value = case != "denied"
    if case == "non_type":
        receivers.resolver.named.return_value = [symbol(kind="function")]
    value = node("new", function=node(value="Service"))
    if case == "qualified":
        value = node("new", function=node(value="Service"), receiver=node(value="pkg"))
    if case == "identifier":
        value = node(value="source")
        receivers.bindings["a.py"] = [ReceiverBinding("source", "Service", scope, node(start=1, end=2))]
    if case == "unknown_value":
        value = node("integer", "0")
    declaration = node("declaration", start=3, end=8, **({} if case == "missing_value" else {"right": value}))
    binding = ReceiverBinding("service", "Service", scope, declaration, inferred=case == "inferred")

    result = receivers._declared_types(syntax, binding, request)

    assert result == ([] if case in {"denied", "non_type", "unknown_value"} else [target])


@pytest.mark.parametrize("case", ["same", "other", "other_member", "qualified", "ambiguous"])
def test_prototype_member_write_invalidates_only_matching_type_identity(indexed, case):
    receivers, syntax, request, scope = indexed
    binding = ReceiverBinding("service", "Service", scope, node(start=2, end=8))
    write = node("assignment", start=30, end=40, left=node("attribute", ("pkg.Service" if case == "qualified" else "Service") + ".prototype." + ("stop" if case == "other_member" else "run")))
    syntax.nodes.append(write)
    target = symbol(kind="class")
    def named(context):
        if context.name != "Service":
            return []
        if context.call.start_byte == 2:
            return [target]
        return [symbol(key="other", kind="class")] if case == "other" else [target]

    receivers.resolver.named.side_effect = named
    receivers.resolver.qualified.side_effect = lambda context: [target] if context.name == "Service" and context.qualifier == "pkg" else []
    if case == "ambiguous":
        receivers.resolver.named.side_effect = None
        receivers.resolver.named.return_value = [target, symbol(key="second", kind="class")]

    result = receivers._declared_types(syntax, binding, request)

    assert result == ([target, symbol(key="second", kind="class")] if case == "ambiguous" else
                      [target] if case in {"other", "other_member"} else [])


@pytest.mark.parametrize("case", ["matching", "wrong_type", "duplicate", "reassigned", "outside_constructor"])
def test_constructor_injection_allows_only_one_unchanged_matching_parameter(indexed, case):
    receivers, syntax, _, scope = indexed
    field = ReceiverBinding("client", "Client", scope, node(start=1, end=2), member=True)
    parameter = ReceiverBinding("dependency", "Other" if case == "wrong_type" else "Client", scope, node(start=11, end=12))
    write = node("assignment", start=20, end=25, left=node("attribute", "this.client"), right=node(value="dependency"))
    constructor = node("method_definition" if case == "outside_constructor" else "constructor_declaration", start=10, end=50, children=[write])
    node("class_declaration", children=[constructor])
    receivers.bindings["a.py"] = [field, parameter] + ([parameter] if case == "duplicate" else [])
    syntax.nodes = [write]
    if case == "reassigned":
        syntax.nodes.append(node("assignment", start=30, left=node(value="dependency")))

    assert receivers._reassigned(syntax, field, "this.client") is (case != "matching")
