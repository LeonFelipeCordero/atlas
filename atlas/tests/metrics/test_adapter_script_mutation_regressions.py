"""Shared script policy regressions, including bounded alias convergence checks."""

from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import javascript, script_resolution as script, typescript
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


@pytest.mark.parametrize("path", ["./tools", ".tools", "pkg/tools"])
def test_default_paths_distinguish_relative_slash_paths_from_packages(path):
    caller = parsed("app/main.py")
    relative = parsed("app/tools.py")
    dotted = parsed("tools.py")
    package = parsed("pkg/tools.py")
    expected = {"./tools": relative, ".tools": dotted, "pkg/tools": package}
    assert ResolutionAdapter().paths(caller, path, [relative, dotted, package]) == [expected[path]]


@pytest.mark.parametrize("kind, expected", [("module", True), ("class", False), ("function", False)])
def test_only_modules_allow_implicit_static_members(kind, expected):
    assert ResolutionAdapter().static_member(symbol(kind=kind)) is expected


def test_alias_fixed_point_stops_on_equality_without_hanging(monkeypatch):
    calls = []

    def targets(nodes, receivers):
        calls.append(set(receivers))
        assert len(calls) <= 3, "alias closure did not terminate on equality"
        return {"this", "alias"}

    monkeypatch.setattr(script, "_lexical_alias_targets", targets)
    initial = {"this"}
    assert script._lexical_aliases([], initial) == {"this", "alias"}
    assert calls == [{"this"}, {"this", "alias"}]
    assert initial == {"this"}


def test_alias_fixed_point_follows_reverse_order_chains():
    assignments = [node("assignment", left=node(value=left), right=node(value=right))
                   for left, right in [("last", "middle"), ("middle", "this")]]
    assert script._lexical_aliases(assignments, {"this"}) == {"this", "middle", "last"}


@pytest.mark.parametrize("family", ["python", "javascript"])
def test_receiver_scope_includes_start_excludes_end_and_adds_only_python_receiver(family):
    parent = symbol("Owner", start=10, end=90, kind="class")
    receiver = node(value="instance")
    method = node("function_definition" if family == "python" else "method_definition", start=20, end=80,
                  parameters=node("parameters", children=[receiver]))
    body = node("block", start=15, end=85, children=[method])
    owner = node("class_definition", start=10, end=90, body=body)
    outside = node("identifier", start=90, end=91)
    adapter = SimpleNamespace(family=family, self_qualifiers={"self"} if family == "python" else {"this"})
    state = syntax(adapter=adapter, nodes=[owner, method, outside])
    scopes = script._receiver_scopes(state, parent)
    assert [n for nodes, _ in scopes for n in nodes] == [owner, method]
    assert scopes[0][1] == ({"self"} if family == "python" else {"this"})
    assert scopes[1][1] == ({"self", "instance"} if family == "python" else {"this"})
    assert script._receiver_scopes(state, parent) is scopes


@pytest.mark.parametrize("relationship", ["direct", "decorated", "foreign", "orphan"])
def test_python_method_receiver_requires_matching_class_parent(relationship):
    method = node("function_definition", parameters=node("parameters", children=[node(value="receiver: Owner")]))
    if relationship != "orphan":
        child = node("decorated_definition", children=[method]) if relationship == "decorated" else method
        node("class_definition", start=99 if relationship == "foreign" else 10,
             body=node("block", children=[child]))
    assert script._method_receiver(method, symbol(start=10)) == (
        "receiver" if relationship in {"direct", "decorated"} else None)


@pytest.mark.parametrize("parameters", [None, node("parameters"), node("parameters", children=[node(value="self: Owner")])])
def test_first_receiver_handles_missing_and_empty_parameters(parameters):
    assert script._first_receiver(node("function_definition", parameters=parameters)) == (
        "self" if parameters and parameters.named_children else None)


@pytest.mark.parametrize("kind", ["method_definition", "function_declaration", "arrow_function"])
def test_javascript_receiver_aliases_do_not_leak_between_methods(kind):
    first = node(kind, start=20, end=40)
    second = node(kind, start=50, end=70)
    alias = node("assignment_expression", start=25, end=30, left=node(value="that"), right=node(value="this"))
    first.children.append(alias)
    alias.parent = first
    write = node("assignment_expression", start=55, end=60, left=node(value="that.run"), right=node(value="other"))
    write.parent = second
    node("class_declaration", start=10, end=90, body=node("class_body", children=[first, second]))
    state = syntax(adapter=javascript.JavaScriptResolution(), nodes=[alias, write])
    assert not script._instance_member_write(state, symbol(start=10, end=90), "run")
    write.parent = first
    state.receiver_scope_cache.clear()
    assert script._instance_member_write(state, symbol(start=10, end=90), "run")


def test_typescript_single_body_selection_does_not_require_duplicate_group_logic():
    candidate = symbol()
    state = syntax(declarations={(10, 20): node("method_definition", body=node("statement_block"))})
    identity = SimpleNamespace(syntax={candidate.file_path: state})
    assert typescript.TypeScriptResolution().select(identity, request(), [candidate]) == [candidate]
    assert typescript.TypeScriptResolution().select(identity, request(), []) == []


def test_typescript_expression_body_callback_is_a_single_executable_target():
    candidate = symbol(kind="function")
    declaration = node("arrow_function", body=node(value="result"))
    state = syntax(declarations={(10, 20): declaration})
    identity = SimpleNamespace(syntax={candidate.file_path: state})
    assert typescript.TypeScriptResolution().select(identity, request(), [candidate]) == [candidate]
