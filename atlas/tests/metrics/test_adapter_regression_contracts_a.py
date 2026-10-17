"""Conservative adapter API contracts and dispatch boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from atlas.metrics.adapters import elixir, go, java, javascript, kotlin
from atlas.metrics.adapters.callable_selection import (
    TypeContext,
    _annotation_node,
    _argument,
    call_arguments,
    callable_parameters,
    expression_type,
    incompatible,
    proven_type,
)
from atlas.syntax import text
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax
from tests.metrics.test_adapter_regression_syntax_a import source_syntax


@pytest.mark.parametrize("missing", ["annotation", "node", "both"])
def test_type_proof_requires_both_annotation_and_node(missing):
    context = TypeContext(syntax(adapter=kotlin.KotlinResolution()), set())
    assert (
        proven_type(
            context,
            None if missing != "node" else "String",
            None if missing != "annotation" else node(),
        )
        is None
    )


@pytest.mark.parametrize("family", ["java", "kotlin"])
@pytest.mark.parametrize(
    "actual, expected",
    [(None, "String"), ("String", None), (None, None), ("String", "String")],
)
def test_unknown_or_equal_types_cannot_prove_incompatibility(family, actual, expected):
    assert incompatible(actual, expected, family) is False


def test_kotlin_lexical_type_uses_smallest_visible_scope():
    state = source_syntax(
        "kotlin",
        "fun f(value: String) { if (true) { val value: Int = 1; use(value) }; use(value) }",
        kotlin.KotlinResolution(),
    )
    uses = [n for n in state.nodes if n.type == "value_argument"]
    assert [
        expression_type(TypeContext(state, set()), n.named_children[0]) for n in uses
    ] == ["Int", "String"]


def test_lossy_annotation_includes_own_start_but_not_next_declaration():
    state = source_syntax(
        "kotlin",
        'val nullable: String? = null\nval plain: String = "x"',
        kotlin.KotlinResolution(),
    )
    annotations = []
    for n in state.nodes:
        if n.type == "nullable_type":
            annotations.append(n)
        elif n.type == "user_type" and text(n) == "String":
            assert n.parent is not None
            if n.parent.type != "nullable_type":
                annotations.append(n)
    context = TypeContext(state, set())
    assert proven_type(context, "String", annotations[0]) is None
    assert proven_type(context, "String", annotations[-1]) == "String"


def test_annotation_range_excludes_type_starting_at_its_end():
    declaration = node("property_declaration", start=10, end=30)
    following = node("generic_type", "List<String>", start=30, end=42)

    assert _annotation_node(following, declaration) is False


@pytest.mark.parametrize("function", [call_arguments, callable_parameters])
def test_jvm_missing_nodes_are_unknown(function):
    assert function(None) is None


@pytest.mark.parametrize(
    "source", ["class A { void f( {}", "class A { void f() { run(; } }"]
)
def test_jvm_error_nodes_have_no_trusted_shape(source):
    from tree_sitter_language_pack import get_parser

    root = get_parser("java").parse(source.encode()).root_node
    assert root.has_error
    assert call_arguments(root) is None
    assert callable_parameters(root) is None


def test_parameter_container_rejects_non_callable_real_nodes():
    state = source_syntax("java", "class A { void f() {} }", java.JavaResolution())
    assert state.root is not None
    assert callable_parameters(state.root) is None
    assert _argument(state.root) is None


def test_empty_value_argument_is_unknown_not_an_index_error():
    # The extractor also accepts recovered syntax nodes from incomplete editor input.
    assert _argument(node("value_argument", named=[])) is None


@pytest.mark.parametrize("qualifier", [None, "", "Tools"])
def test_elixir_qualified_dispatch_normalizes_absent_qualifier(qualifier):
    file = parsed(language="elixir")
    targets = [symbol("Tools", kind="module")]
    resolver = SimpleNamespace(
        modules=SimpleNamespace(declared=Mock(return_value=targets)),
        members=Mock(return_value=[]),
    )
    assert (
        elixir.ElixirResolution().qualified(
            resolver, request(file, qualifier=qualifier)
        )
        == []
    )
    resolver.modules.declared.assert_called_once_with(file, qualifier or "")
    resolver.members.assert_called_once_with(targets, "run", True)


@pytest.mark.parametrize(
    "source, expected",
    [
        ("alias Tools.Brew", "Tools.Brew"),
        ("import Tools.Brew", "Tools.Brew"),
        ('use "local/tool"', "local/tool"),
        (" raw/path ", "raw/path"),
    ],
)
def test_elixir_import_path_preserves_quoted_declared_and_raw_paths(source, expected):
    assert elixir.ElixirResolution().import_path(source) == expected


def test_elixir_argument_lookup_supports_field_and_child_fallback():
    state = source_syntax("elixir", "run(1, 2)", elixir.ElixirResolution())
    call = next(n for n in state.nodes if n.type == "call")
    assert elixir.arity(call) == 2
    args = elixir.arguments(call)
    assert args is not None
    assert elixir.arguments(args) is None
    assert elixir.arguments(None) is None
    # The documented cross-grammar child fallback must retain the same container.
    fallback = node("arguments", children=[node("integer", "1")])
    assert elixir.arguments(node("call", children=[fallback])) == fallback


def test_elixir_clause_index_handles_unavailable_or_non_declaration_heads():
    adapter = elixir.ElixirResolution()
    file = parsed(language="elixir", symbols=[symbol(language="elixir")])
    cache = {file.source.path: syntax()}
    repository = SimpleNamespace(symbols=file.symbols)
    assert adapter.clauses(repository, cache) == {file.symbols[0].key: (0, 0, False)}
    empty = node("call", arguments=node("arguments", named=[]))
    cache[file.source.path].node = lambda start, end: empty
    assert adapter.clauses(repository, cache) == {file.symbols[0].key: (0, 0, False)}


@pytest.mark.parametrize("missing", ["node", "receiver", "parameter"])
def test_go_receiver_lookup_rejects_missing_syntax(missing):
    method = symbol(kind="method")
    declaration = (
        None
        if missing == "node"
        else node(
            "method_declaration",
            **(
                {"receiver": node("parameter_list", named=[])}
                if missing == "parameter"
                else {}
            ),
        )
    )
    resolver = SimpleNamespace(
        syntax={
            method.file_path: syntax(
                declarations={(method.start_byte, method.end_byte): declaration}
            )
        }
    )
    assert (
        go.GoResolution()._receiver_method(
            resolver, method, symbol("Owner", kind="type")
        )
        is False
    )


@pytest.mark.parametrize("kind, parent", [("function", "Owner"), ("method", "Other")])
def test_javascript_duplicate_selection_requires_one_method_group(kind, parent):
    adapter = javascript.JavaScriptResolution()
    candidates = [
        symbol(kind=kind, start=10, parent="Owner"),
        symbol(kind=kind, start=30, parent=parent),
    ]
    declarations = {
        (s.start_byte, s.end_byte): node(
            "method_definition" if kind == "method" else "function_declaration",
            body=node("statement_block"),
        )
        for s in candidates
    }
    identity = SimpleNamespace(
        syntax={candidates[0].file_path: syntax(declarations=declarations)}
    )
    assert javascript._method_group(candidates) is False
    assert adapter.select(identity, request(), candidates) == []


@pytest.mark.parametrize(
    "class_rebound, prototype_rebound, expected",
    [(False, False, True), (True, False, False), (False, True, False)],
)
def test_javascript_receiver_type_requires_stable_class_and_prototype(
    class_rebound, prototype_rebound, expected
):
    state = syntax()
    state.member_rebound = lambda name, member: (
        class_rebound if name == "Owner" else prototype_rebound
    )
    assert (
        javascript.JavaScriptResolution().receiver_type_allowed(state, "Owner", "run")
        is expected
    )


@pytest.mark.parametrize(
    "path, expected",
    [
        ("./tools", True),
        ("../tools", True),
        ("package/tools", False),
        ("package", False),
        (".", False),
    ],
)
def test_javascript_path_dispatch_requires_relative_slash(path, expected):
    source = parsed("src/main.js", "javascript")
    local = parsed("src/tools.js", "javascript")
    parent = parsed("tools.js", "javascript")
    files = [
        source,
        local,
        parent,
        parsed("src/package/tools.js", "javascript"),
        parsed("src/index.js", "javascript"),
    ]
    matches = javascript.JavaScriptResolution().paths(source, path, files)
    assert matches == ([parent if path.startswith("..") else local] if expected else [])


@pytest.mark.parametrize(
    "source, expected",
    [
        ("import { type A } from './tools'", True),
        ("import Default, { type A } from './tools'", False),
        ("import Default from './tools'", False),
        ("import './tools'", False),
    ],
)
def test_typescript_type_only_named_clause_excludes_mixed_default_imports(
    source, expected
):
    from tree_sitter_language_pack import get_parser

    root = get_parser("typescript").parse(source.encode()).root_node
    assert not root.has_error
    assert (
        javascript.JavaScriptResolution().import_type_only(root.named_children[0])
        is expected
    )


def test_javascript_export_range_does_not_include_next_symbol():
    adapter = javascript.JavaScriptResolution()
    state = source_syntax(
        "javascript", "export function first() {}function second() {}", adapter
    )
    declarations = [n for n in state.nodes if n.type == "function_declaration"]
    first = symbol(
        "first",
        path=state.file.source.path,
        start=declarations[0].start_byte,
        end=declarations[0].end_byte,
    )
    assert declarations[1].start_byte == declarations[0].end_byte
    boundary = symbol(
        "second",
        path=state.file.source.path,
        start=declarations[1].start_byte,
        end=declarations[1].end_byte,
    )
    state.file.symbols = [first, boundary]
    assert javascript.export_bindings(state.file, state) == {"first": [first]}
