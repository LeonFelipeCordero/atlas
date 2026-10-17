"""Repository-local resolution policies with syntax and adapter boundaries stubbed."""

from dataclasses import asdict
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from atlas.domain.models import Import, Inheritance, ParsedRepository
from atlas.metrics import resolver as module
from atlas.metrics.resolution_contract import CallTarget, ResolutionRequest
from atlas.metrics.resolver import CallResolver
from tests.metrics.resolution_support import call, node, parsed_file, symbol


@pytest.fixture
def context(monkeypatch):
    file = parsed_file()
    resolver: Any = CallResolver.__new__(CallResolver)
    resolver.repository = ParsedRepository([file])
    resolver.files = {"a.py": file}
    resolver.symbols = {}
    syntax = SimpleNamespace(shadowed=Mock(return_value=False), member_rebound=Mock(return_value=False),
                             node=Mock(return_value=None), static=Mock(return_value=False), import_node=Mock(return_value=None))
    resolver.syntax = {"a.py": syntax}
    resolver.imports = SimpleNamespace(get=Mock(return_value=None))
    resolver.modules = SimpleNamespace(same_package=Mock(return_value=[]))
    resolver.receivers = SimpleNamespace(resolve=Mock(return_value=None))
    resolver.identity = SimpleNamespace(select=Mock(side_effect=lambda file, call, matches: matches))
    adapter = SimpleNamespace(skip_type_scope=False, family="python", macro_nodes={"macro"},
                              call_target=Mock(return_value=(None, None)),
                              normalized_call=Mock(return_value=CallTarget(None, None, "run", None)),
                              constructors={"new"}, receiver_rejected=Mock(return_value=False),
                              receiver_names=set(), self_qualifiers={"self"},
                              import_path=lambda source: source.removeprefix("import "),
                              import_targets=Mock(return_value=[("pkg", "file:pkg.py")]),
                              import_type_only=Mock(return_value=True), require_import_node=False)
    monkeypatch.setattr(module, "get_resolution_adapter", lambda language: adapter)
    return resolver, file, syntax, adapter


def test_owner_uses_smallest_containing_span_including_exact_boundaries(context):
    resolver, file, _, _ = context
    outer = symbol(key="outer", start=0, end=100)
    inner = symbol(key="inner", start=20, end=25)
    file.symbols = [outer, inner, symbol(key="overlap", start=21, end=30)]

    assert resolver.owner(call()) == inner
    assert resolver.owner(call(start=101, end=102)) is None


def test_ancestors_stops_on_cycle(context):
    resolver, _, _, _ = context
    first, second = symbol(key="a", parent="b"), symbol(key="b", parent="a")
    resolver.symbols = {"a": first, "b": second}

    assert resolver.ancestors(first) == [first, second]


def test_lexical_prefers_nearest_scope_and_ignores_unrelated_nested_declarations(context):
    resolver, file, _, _ = context
    owner = symbol(key="owner")
    local = symbol(key="local", parent="owner")
    global_ = symbol(key="global")
    file.symbols = [symbol(key="unrelated", parent="elsewhere"), global_, local]
    resolver.symbols = {"owner": owner}

    assert resolver.lexical(file, "run", owner) == [local]
    assert resolver.lexical(file, "run", None) == [global_]


def test_type_scope_can_be_skipped_by_language_policy(context):
    resolver, file, _, adapter = context
    owner = symbol(key="class", kind="class")
    resolver.symbols = {"class": owner}
    file.symbols = [symbol(key="member", parent="class"), symbol(key="global")]
    adapter.skip_type_scope = True

    assert resolver.lexical(file, "run", owner) == [symbol(key="global")]


@pytest.mark.parametrize(("start", "namespace", "expected"), [(0, False, []), (1, False, ["local"]), (0, True, [])])
def test_module_import_masks_top_level_local_only_at_zero_position(context, start, namespace, expected):
    resolver, file, _, _ = context
    file.symbols = [symbol(key="local")]
    resolver.imports.get.return_value = SimpleNamespace(start=start, namespace=namespace, targets=[symbol(key="imported")])

    result = resolver.named(ResolutionRequest(file, call(), None, "run"))

    assert [s.key for s in result] == expected


def test_shadowed_name_blocks_local_import_and_fallback(context):
    resolver, file, syntax, _ = context
    file.symbols = [symbol()]
    syntax.shadowed.return_value = True

    assert resolver.named(ResolutionRequest(file, call(), None, "run"), fallback=True) == []
    resolver.modules.same_package.assert_not_called()


@pytest.mark.parametrize(("namespace", "expected"), [(False, ["imported"]), (True, [])])
def test_import_binding_does_not_treat_namespace_as_callable(context, namespace, expected):
    resolver, file, _, _ = context
    resolver.imports.get.return_value = SimpleNamespace(namespace=namespace, targets=[symbol(key="imported")])

    assert [s.key for s in resolver.named(ResolutionRequest(file, call(), None, "run"))] == expected


def test_same_package_precedes_opt_in_global_fallback(context):
    resolver, file, _, _ = context
    resolver.modules.same_package.return_value = [symbol(key="package")]

    assert resolver.named(ResolutionRequest(file, call(), None, "run"), fallback=True) == [symbol(key="package")]


def test_global_fallback_excludes_types_and_requires_opt_in(context):
    resolver, file, _, _ = context
    hidden = symbol(parent="unrelated")
    file.symbols = [hidden, symbol(key="type", kind="class", parent="unrelated")]
    request = ResolutionRequest(file, call(), None, "run")

    assert resolver.named(request) == []
    assert resolver.named(request, fallback=True) == [hidden]


@pytest.mark.parametrize("count", [0, 2])
def test_members_rejects_missing_or_ambiguous_type_before_adapter(context, count):
    resolver, _, _, _ = context

    assert resolver.members([symbol(kind="class")] * count, "run", False) == []


@pytest.mark.parametrize(("static", "expected"), [(False, ["instance", "static"]), (True, ["static"])])
def test_members_applies_static_filter_only_for_class_access(context, static, expected):
    resolver, _, syntax, adapter = context
    owner = symbol(kind="class")
    instance, static_method = symbol(key="instance"), symbol(key="static")
    adapter.member_overwritten = Mock(return_value=False)
    adapter.instance_members = Mock(return_value=[instance, static_method])
    adapter.static_member = Mock(return_value=False)
    syntax.static.side_effect = lambda declaration: declaration.key == "static"

    result = resolver.members([owner], "run", static)

    assert [declaration.key for declaration in result] == expected
    adapter.instance_members.assert_called_once_with(resolver, owner, "run")


def test_overwritten_member_cannot_resolve_to_original_declaration(context):
    resolver, _, _, adapter = context
    adapter.member_overwritten = Mock(return_value=True)
    adapter.instance_members = Mock(return_value=[symbol()])

    assert resolver.members([symbol(kind="class")], "run", False) == []
    adapter.instance_members.assert_not_called()


def test_typed_receiver_rejection_is_not_replaced_with_qualified_guess(context, monkeypatch):
    resolver, file, _, _ = context
    resolver.receivers.resolve.return_value = []
    qualified = Mock(return_value=[symbol()])
    monkeypatch.setattr(resolver, "qualified", qualified)
    request = ResolutionRequest(file, call(), None, "run", "service")

    assert resolver._matches(request, None, CallTarget(None, node(), "run", "service")) == []
    qualified.assert_not_called()


def test_member_rebinding_prevents_typed_resolution(context):
    resolver, file, syntax, _ = context
    syntax.member_rebound.return_value = True

    assert resolver._typed_matches(ResolutionRequest(file, call(), None, "run", "service")) is None
    resolver.receivers.resolve.assert_not_called()


def test_macro_calls_stop_before_target_normalization(context):
    resolver, _, syntax, adapter = context
    syntax.node.return_value = node("macro")

    assert resolver.resolve(call(), None) == []
    adapter.call_target.assert_not_called()


def test_scoped_call_spelling_normalizes_context_and_filters_non_callables(context, monkeypatch):
    resolver, file, _, adapter = context
    adapter.normalized_call.return_value = CallTarget(None, None, "pkg::run", None)
    selected, module_target = symbol(), symbol(key="module", kind="module")
    matches = Mock(return_value=[selected, symbol(key="variable", kind="variable"), module_target])
    monkeypatch.setattr(resolver, "_matches", matches)
    resolver.identity.select = Mock(return_value=[selected])
    site = call()

    result = resolver.resolve(site, None)

    assert result == [selected]
    assert matches.call_args.args[0] == ResolutionRequest(file, site, None, "run", "pkg")
    resolver.identity.select.assert_called_once_with(file, site, [selected, module_target])


@pytest.mark.parametrize(("directive", "required", "expected_target", "confidence"), [
    (None, False, "file:pkg.py", "INFERRED"), (None, True, "external:pkg", "EXTRACTED"),
    (node(start=0), True, "file:pkg.py", "INFERRED"),
])
def test_import_connection_keeps_evidence_type_only_and_required_node_policy(context, directive, required, expected_target, confidence):
    resolver, _, syntax, adapter = context
    syntax.import_node.return_value = directive
    adapter.require_import_node = required
    external = Mock(side_effect=lambda language, kind, name: "external:" + name)

    connections = module._import_connections(Import("a.py", "import pkg", 3), resolver, external)

    assert [asdict(edge) for edge in connections] == [{
        "source_key": "file:a.py", "target_key": expected_target, "type": "IMPORTS", "confidence": confidence,
        "path": "a.py", "line": 3, "evidence": "import pkg", "type_only": True}]
    assert adapter.import_targets.call_args.args[1].position == (0 if directive else None)


def test_call_connections_preserves_reference_relationship_and_file_fallback(context, monkeypatch):
    resolver, file, _, _ = context
    site = call()
    site.relationship = "REFERENCES"
    monkeypatch.setattr(resolver, "resolve", Mock(return_value=[]))
    external = Mock(return_value="external:python:callable:run")

    result = module._call_connections(site, resolver, external)

    assert [asdict(edge) for edge in result] == [{
        "source_key": "file:a.py", "target_key": "external:python:callable:run", "type": "REFERENCES",
        "confidence": "INFERRED", "path": "a.py", "line": 3, "evidence": "run()", "type_only": False}]
    external.assert_called_once_with(file.source.language, "callable", "run")


@pytest.mark.parametrize(("count", "expected"), [(0, "external"), (1, "base0"), (2, "external")])
def test_inheritance_requires_unique_target(context, monkeypatch, count, expected):
    resolver, file, _, _ = context
    file.inheritances = [Inheritance("derived", "a.py", "python", "Base", 4, "class Derived(Base)")]
    monkeypatch.setattr(module, "_inheritance_targets", Mock(return_value=[symbol(key=f"base{i}") for i in range(count)]))

    result = module._resolve_inheritances(resolver.repository, resolver, Mock(return_value="external"))

    assert [asdict(edge) for edge in result] == [{
        "source_key": "derived", "target_key": expected, "type": "INHERITS", "confidence": "INFERRED",
        "path": "a.py", "line": 4, "evidence": "class Derived(Base)", "type_only": False}]


def test_resolve_connections_deduplicates_external_calls_and_preserves_order(context, monkeypatch):
    resolver, file, _, _ = context
    later = call(start=30, end=35)
    later.line = 7
    file.calls = [call(), later]
    monkeypatch.setattr(resolver, "resolve", Mock(return_value=[]))
    monkeypatch.setattr(module, "CallResolver", Mock(return_value=resolver))

    graph = module.resolve_connections(resolver.repository)

    assert [edge.line for edge in graph.connections] == [3, 7]
    assert [edge.target_key for edge in graph.connections] == ["external:python:callable:run"] * 2
    assert [asdict(external) for external in graph.external_nodes] == [{
        "key": "external:python:callable:run", "language": "python", "kind": "callable", "name": "run"}]


def test_resolved_call_connects_enclosing_callable_to_internal_target(context, monkeypatch):
    resolver, file, _, _ = context
    enclosing = symbol(key="caller", start=0, end=100)
    target = symbol(key="callee", start=200, end=250)
    file.symbols = [enclosing, target]
    site = call()
    file.calls = [site]
    resolved = Mock(return_value=[target])
    monkeypatch.setattr(resolver, "resolve", resolved)
    monkeypatch.setattr(module, "CallResolver", Mock(return_value=resolver))

    graph = module.resolve_connections(resolver.repository)

    assert [asdict(edge) for edge in graph.connections] == [{
        "source_key": "caller", "target_key": "callee", "type": "CALLS",
        "confidence": "INFERRED", "path": "a.py", "line": 3,
        "evidence": "run()", "type_only": False}]
    assert graph.external_nodes == []
    resolved.assert_called_once_with(site, enclosing)


def test_public_resolution_orders_relationships_and_keeps_external_kinds_distinct(context, monkeypatch):
    resolver, file, _, adapter = context
    file.imports = [Import("a.py", "run", 1)]
    file.inheritances = [Inheritance("derived", "a.py", "python", "run", 2, "base run")]
    file.calls = [call()]
    adapter.import_targets.return_value = [("run", None)]
    monkeypatch.setattr(module, "_inheritance_targets", Mock(return_value=[]))
    monkeypatch.setattr(resolver, "resolve", Mock(return_value=[]))
    monkeypatch.setattr(module, "CallResolver", Mock(return_value=resolver))

    graph = module.resolve_connections(resolver.repository)

    assert [(edge.type, edge.target_key, edge.confidence) for edge in graph.connections] == [
        ("IMPORTS", "external:python:module:run", "EXTRACTED"),
        ("INHERITS", "external:python:type:run", "INFERRED"),
        ("CALLS", "external:python:callable:run", "INFERRED")]
    assert [external.kind for external in graph.external_nodes] == ["module", "type", "callable"]
