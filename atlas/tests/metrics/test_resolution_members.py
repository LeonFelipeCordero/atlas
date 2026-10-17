"""Member and scope decisions with adapter boundaries stubbed, not parsed."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from atlas.domain.models import Inheritance, ParsedRepository
from atlas.metrics import resolver as module
from atlas.metrics.resolution_contract import CallTarget, ResolutionRequest
from tests.metrics.resolution_support import call, node, symbol
from tests.metrics.test_resolver import context as context


def test_constructor_builds_repository_indexes_without_parsing(context, monkeypatch):
    _, file, syntax, _ = context
    declaration = symbol()
    file.symbols = [declaration]
    monkeypatch.setattr(module, "Syntax", Mock(return_value=syntax))
    for name in ("Modules", "ImportBindings", "CallableIdentity", "ReceiverTypes"):
        monkeypatch.setattr(module, name, Mock())

    resolver = module.CallResolver(ParsedRepository([file]))

    assert (resolver.files, resolver.symbols, resolver.syntax) == (
        {"a.py": file}, {"target": declaration}, {"a.py": syntax})


def test_inheritance_keeps_only_visible_type_identities(context):
    resolver, file, _, adapter = context
    derived = symbol(key="derived", kind="class", start=10, end=80)
    base = symbol(key="base", name="Base", kind="interface")
    file.symbols = [derived, base, symbol(name="Base")]
    resolver.symbols = {"derived": derived}
    adapter.inheritance = lambda resolver, request, matches: matches

    result = module._inheritance_targets(resolver, Inheritance(
        "derived", "a.py", "python", "Base", 2, "class Derived(Base)"))

    assert result == [base]


def test_class_lookup_applies_language_qualification_before_kind_filter(context):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, _, _, adapter = context
    target = symbol(kind="struct")
    adapter.qualify_class = Mock(return_value=[symbol(kind="function"), target])

    assert resolver.class_named(request) == [target]


@pytest.mark.parametrize("case", ["missing", "wrong_kind", "nested", "disallowed", "allowed"])
def test_constructor_receiver_requires_unqualified_allowed_class(context, case):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, file, _, adapter = context
    target = symbol(name="Service", kind="class")
    file.symbols = [target]
    adapter.receiver_class_nodes = {"new"}
    adapter.receiver_class_allowed = Mock(return_value=case != "disallowed")
    adapter.qualify_class = lambda resolver, request, matches: matches
    adapter.call_target.return_value = (node(value="Service"), node() if case == "nested" else None)
    receiver = None if case == "missing" else node("call" if case == "wrong_kind" else "new")

    assert resolver._receiver_class(request, receiver) == ([target] if case == "allowed" else [])


@pytest.mark.parametrize("case", ["outside", "class_body", "static", "denied", "instance"])
def test_self_requires_instance_method_and_adapter_permission(context, case):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, _, syntax, adapter = context
    owner = symbol(key="class", kind="class")
    method = symbol(key="method", kind="method", parent="class")
    resolver.symbols = {"class": owner, "method": method}
    syntax.static.return_value = case == "static"
    adapter.implicit_receiver = Mock(return_value=case != "denied")
    request = replace(request, owner=None if case == "outside" else owner if case == "class_body" else method)

    assert resolver._self_class(request) == ([owner] if case == "instance" else [])


def test_member_declarations_excludes_wrong_parent_name_and_noncallables(context):
    resolver, file, _, _ = context
    owner = symbol(key="class", kind="class")
    method = symbol(key="method", kind="method", parent="class")
    file.symbols = [method, symbol(parent="other"), symbol(name="other", parent="class"),
                    symbol(kind="variable", parent="class")]

    assert resolver._member_declarations(owner, "run") == [method]


@pytest.mark.parametrize("namespace", [True, False])
def test_local_class_masks_namespace_import_but_local_module_does_not(context, namespace):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, file, _, adapter = context
    local = symbol(name="Service", kind="module" if namespace else "class")
    target = symbol(key="namespace_member")
    file.symbols = [local]
    adapter.local_namespace = Mock(return_value=namespace)
    adapter.qualify_class = lambda resolver, request, matches: matches
    adapter.member_overwritten = Mock(return_value=False)
    adapter.instance_members = Mock(return_value=[symbol(key="class_member")])
    adapter.static_member = Mock(return_value=True)
    binding = Mock(namespace=True)
    binding.member.return_value = [target]
    resolver.imports.get.return_value = binding

    assert resolver.qualified(request) == ([target] if namespace else [symbol(key="class_member")])


@pytest.mark.parametrize("case", ["rebound", "shadowed", "self", "class", "binding", "fallback"])
def test_qualified_resolution_uses_visible_identity_not_member_name(context, case):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, file, syntax, adapter = context
    target, fallback = symbol(key="member"), symbol(key="fallback")
    owner = symbol(name="Service", kind="class")
    syntax.member_rebound.return_value = case == "rebound"
    syntax.shadowed.return_value = case == "shadowed"
    adapter.qualify_class = lambda resolver, request, matches: matches
    adapter.member_overwritten = Mock(return_value=False)
    adapter.instance_members = Mock(return_value=[target])
    adapter.static_member = Mock(return_value=True)
    adapter.qualified = Mock(return_value=[fallback])
    if case == "class":
        file.symbols = [owner]
    if case == "binding":
        resolver.imports.get.return_value = Mock(namespace=False, targets=[owner])
    if case == "self":
        method = symbol(key="method", parent=owner.key, kind="method")
        resolver.symbols = {owner.key: owner}
        adapter.implicit_receiver = Mock(return_value=True)
        request = replace(request, owner=method, qualifier="self")

    expected = [] if case in {"rebound", "shadowed"} else [fallback] if case == "fallback" else [target]
    assert resolver.qualified(request) == expected


@pytest.mark.parametrize("constructor", [True, False])
def test_bare_constructor_does_not_guess_a_global_function(context, constructor):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, file, _, _ = context
    target = symbol(parent="unrelated")
    file.symbols = [target]

    assert resolver._bare(replace(request, qualifier=None), node("new" if constructor else "call")) == (
        [] if constructor else [target])


@pytest.mark.parametrize("qualifier", ["pkg.Service", "pkg::Service", "factory()"])
def test_complex_receiver_uses_qualified_identity_or_constructed_type(context, qualifier, monkeypatch):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, _, _, _ = context
    qualified, constructed = symbol(key="qualified"), symbol(key="constructed")
    monkeypatch.setattr(resolver, "qualified", Mock(return_value=[qualified]))
    monkeypatch.setattr(resolver, "_receiver_class", Mock(return_value=[symbol(kind="class")]))
    monkeypatch.setattr(resolver, "members", Mock(return_value=[constructed]))

    result = resolver._receiver_matches(replace(request, qualifier=qualifier), node("new"))

    assert result == ([constructed] if qualifier == "factory()" else [qualified])


@pytest.mark.parametrize("case", ["rejected", "complex", "qualified", "bare", "unknown"])
def test_call_target_dispatch_preserves_missing_and_rejected_results(context, case, monkeypatch):
    request = ResolutionRequest(context[1], call(), None, "run", "Service")
    resolver, _, _, adapter = context
    adapter.receiver_rejected.return_value = case == "rejected"
    paths = {"complex": "_receiver_matches", "qualified": "qualified", "bare": "_bare"}
    for key, method in paths.items():
        monkeypatch.setattr(resolver, method, Mock(return_value=[symbol(key=key)]))
    receiver = node("new") if case == "complex" else None
    request = replace(request, qualifier="Service" if case in {"rejected", "qualified"} else None)
    site = replace(request.call, bare_target=case != "unknown")

    result = resolver._matches(replace(request, call=site), None, CallTarget(None, receiver, "run", request.qualifier))

    assert result == ([] if case in {"rejected", "unknown"} else [symbol(key=case)])
