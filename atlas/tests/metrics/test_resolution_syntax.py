"""Conservative binding scans with synthetic trees and parser boundary stubs."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from atlas.metrics import resolution_syntax as module
from atlas.metrics.resolution_syntax import Syntax, names
from tests.metrics.resolution_support import node, parsed_file, symbol


@pytest.fixture
def syntax():
    adapter = SimpleNamespace(
        scopes={"function_definition", "block"}, single_parameter_functions={"arrow_function"},
        visible=Mock(return_value=True), declaration_allowed=Mock(return_value=False),
        import_shadowed=Mock(return_value=False), binding=Mock(return_value=(None, None)),
        is_import_node=lambda n: n.type == "import_statement", member_writes={"assignment"},
        write_target=lambda n: n.child_by_field_name("left"), rebound_declarations={"class_definition"},
        static=Mock(return_value=True), lexical_imports=Mock(return_value=[]),
    )
    result = Syntax(parsed_file(), cast(Any, adapter))
    result.root = node("module", end=200)
    return result


@pytest.mark.parametrize("kind", ["attribute", "member_expression", "field_expression", "subscript"])
def test_names_excludes_member_access_even_with_identifier_children(kind):
    assert names(node(kind, children=[node(value="receiver"), node(value="member")])) == set()


def test_names_collects_patterns_without_keys_or_annotations():
    pair = node("pair_pattern", children=[node(value="key"), node(value="bound")])
    pair.child_by_field_name = lambda name: pair.named_children[1] if name == "value" else None
    pattern = node("tuple_pattern", children=[
        pair,
        node("typed_parameter", children=[node(value="arg"), node("type_identifier", "Type")]),
        node(value="arg"),
    ])

    assert names(pattern) == {"bound", "arg"}
    assert names(None) == set()


def test_names_go_parameters_keeps_all_names():
    parameter = node("parameter_declaration")
    parameter.children_by_field_name = lambda name: [node(value="a"), node(value="b")] if name == "name" else []

    assert names(parameter) == {"a", "b"}


def test_root_decodes_invalid_utf8_once(monkeypatch):
    file = parsed_file()
    file.source.source = b"a\xffb"
    parser = Mock()
    root = node("module")
    parser.parse.return_value.root_node = root
    boundary = Mock(return_value=parser)
    monkeypatch.setattr(module, "get_parser", boundary)
    syntax = Syntax(file, cast(Any, SimpleNamespace(scopes=set())))

    assert syntax.root is root
    assert syntax.root is root
    boundary.assert_called_once_with("python")
    parser.parse.assert_called_once_with("a\ufffdb".encode())


def test_parser_failure_is_cached_as_empty_syntax(monkeypatch):
    boundary = Mock(side_effect=RuntimeError("unavailable grammar"))
    monkeypatch.setattr(module, "get_parser", boundary)
    syntax = Syntax(parsed_file(), cast(Any, SimpleNamespace(scopes=set())))

    assert (syntax.root, syntax.nodes, syntax.node(0, 1)) == (None, [], None)
    boundary.assert_called_once_with("python")


def test_span_lookup_requires_both_exact_coordinates(syntax):
    child = node(start=10, end=15)
    syntax.root = node("module", children=[child])

    assert (syntax.node(10, 15), syntax.node(10, 14), syntax.node(9, 15)) == (child, None, None)


def test_scope_uses_nearest_ancestor_not_node_itself(syntax):
    leaf = node()
    block = node("block", children=[leaf])
    outer = node("function_definition", children=[block])
    syntax.root = node("module", children=[outer])

    assert (syntax.scope(leaf), syntax.scope(block), syntax.scope(outer)) == (block, outer, syntax.root)


@pytest.mark.parametrize("case", [(10, True, True), (19, True, True), (20, True, False), (9, True, False), (15, False, False)])
def test_visible_uses_half_open_scope_and_adapter_policy(syntax, case):
    position, visible, expected = case
    syntax.adapter.visible.return_value = visible

    assert syntax._visible(node("block", start=10, end=20), position) is expected


def test_parameter_and_single_parameter_bindings_use_function_scope(syntax):
    parameter = node(value="arg")
    parameters = node("parameters", children=[parameter])
    function = node("function_definition", children=[parameters])
    single = node(value="single")
    arrow = node("arrow_function", parameter=single)
    syntax.nodes = [parameters, arrow]

    assert syntax.bindings == [("arg", function, parameters), ("single", arrow, single)]


@pytest.mark.parametrize("case", [(10, False, True), (20, False, False), (10, True, False)])
def test_shadowed_respects_visibility_and_allowed_declaration(syntax, case):
    position, allowed, expected = case
    declaration = node("assignment", start=2, end=5)
    syntax.bindings = [("run", node("block", start=0, end=20), declaration)]
    declarations = [symbol(start=2, end=5)] if allowed else []

    assert syntax.shadowed("run", position, declarations) is expected


def test_import_shadowing_wins_over_allowed_declaration(syntax):
    syntax.adapter.import_shadowed.return_value = True
    syntax.bindings = []

    assert syntax.shadowed("run", 10, [symbol()]) is True


def test_import_lookup_disambiguates_source_and_rejects_ambiguous_line(syntax):
    first = node("import_statement", "import one;")
    second = node("import_statement", "import two")
    syntax.nodes = [first, second]

    assert (syntax.import_node(1), syntax.import_node(1, " import one "),
            syntax.import_node(2), syntax.import_scope(2)) == (None, first, None, syntax.root)


def test_member_writes_remove_spaces_and_match_complete_member(syntax):
    syntax.nodes = [node("assignment", left=node("attribute", " service . run "))]

    assert (syntax.member_rebound("service", "run"), syntax.member_rebound("service", "runner")) == (True, False)


def test_binding_scan_uses_adapter_target_and_scope_override(syntax):
    target = node("tuple_pattern", children=[node(value="first"), node(value="second")])
    declaration = node("declaration", left=target)
    outer = node("function_definition", children=[declaration])
    syntax.adapter.binding.return_value = (target, outer)
    syntax.nodes = [declaration, node("arrow_function", parameters=node("parameters"))]

    assert sorted(syntax.bindings, key=lambda binding: binding[0]) == [
        ("first", outer, declaration), ("second", outer, declaration)]


def test_import_cache_and_scope_use_adapter_imports_and_enclosing_scope(syntax):
    directive = node("import_statement", "import pkg")
    owner = node("function_definition", children=[directive])
    syntax.nodes = [directive]
    syntax.adapter.lexical_imports.return_value = [("pkg", directive)]

    assert (syntax.imports, syntax.import_scope(1, "import pkg")) == ([("pkg", directive)], owner)


@pytest.mark.parametrize("scenario", [
    ("same_class", 0, 100), ("other_class", 100, 200), ("start_mismatch", 1, 100),
    ("nested_function", 0, 100), ("declaration", 0, 100), ("other_name", 0, 100), ("orphan", 0, 100),
])
def test_class_rebinding_only_counts_writes_directly_in_matching_class(syntax, scenario):
    case, start, end = scenario
    write = node("class_definition" if case == "declaration" else "assignment", start=10, end=15)
    if case == "nested_function":
        child = node("function_definition", start=5, end=20, children=[write])
    else:
        child = write
    if case != "orphan":
        node("class_definition", start=start, end=end, children=[child])
    syntax.bindings = [("other" if case == "other_name" else "run", syntax.root, write)]

    assert syntax.class_rebound(symbol(kind="class"), "run") is (case == "same_class")


def test_static_delegates_symbol_and_syntax(syntax):
    declaration = symbol()

    assert syntax.static(declaration) is True
    syntax.adapter.static.assert_called_once_with(syntax, declaration)
