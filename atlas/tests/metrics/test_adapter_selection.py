"""Executable selection uses call shape without guessing ambiguous targets."""

from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import elixir, java, javascript, kotlin, python, typescript
from atlas.metrics.adapters.callable_selection import (
    Argument,
    CallContext,
    Parameter,
    TypeContext,
    accepts,
    incompatible,
    proven_type,
)
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


@pytest.fixture
def selection_case():
    def build(kinds, *, adapter=None, bodies=None, statics=None):
        adapter = adapter or typescript.TypeScriptResolution()
        file = parsed()
        symbols = [
            symbol(start=10 + i * 10, kind="method", parent="class:Owner")
            for i in range(len(kinds))
        ]
        bodies = bodies if bodies is not None else [False] * (len(kinds) - 1) + [True]
        nodes = [
            node(
                kind,
                start=s.start_byte,
                end=s.end_byte,
                **({"body": node("block")} if body else {}),
            )
            for s, kind, body in zip(symbols, kinds, bodies)
        ]
        cache = syntax(
            adapter=adapter,
            declarations={
                (s.start_byte, s.end_byte): n for s, n in zip(symbols, nodes)
            },
            static=lambda s: (statics or {}).get(s.start_byte, False),
        )
        return SimpleNamespace(syntax={file.source.path: cache}), request(file), symbols

    return build


def test_typescript_selects_only_body_after_signatures(selection_case):
    identity, call, symbols = selection_case(["method_signature", "method_definition"])
    assert typescript.TypeScriptResolution().select(
        identity, call, list(reversed(symbols))
    ) == [symbols[1]]


@pytest.mark.parametrize(
    ("kinds", "bodies", "statics", "expected"),
    [
        (["method_signature"], [False], {}, []),
        (["method_definition"], [True], {}, [0]),
        (["method_definition", "method_definition"], [True, True], {}, []),
        (["method_definition", "method_signature"], [True, False], {}, []),
        (["property_signature", "method_definition"], [False, True], {}, []),
        (["method_signature", "method_definition"], [False, True], {20: True}, []),
        (["method_signature", "method_signature"], [False, False], {}, []),
    ],
)
def test_typescript_rejects_non_executable_or_inconsistent_groups(
    selection_case, kinds, bodies, statics, expected
):
    identity, call, symbols = selection_case(kinds, bodies=bodies, statics=statics)
    result = typescript.TypeScriptResolution().select(identity, call, symbols)
    assert result == [symbols[i] for i in expected]


@pytest.mark.parametrize("change", ["missing", "parent", "name", "file"])
def test_typescript_does_not_merge_missing_or_unrelated_declarations(
    selection_case, change
):
    identity, call, symbols = selection_case(["method_signature", "method_definition"])
    if change == "missing":
        identity.syntax[call.file.source.path].node = lambda start, end: None
    elif change == "parent":
        symbols[1].parent_key = "class:Other"
    elif change == "name":
        symbols[1].name = "other"
    else:
        symbols[1].file_path = "other.ts"
        identity.syntax["other.ts"] = identity.syntax[call.file.source.path]
    assert typescript.TypeScriptResolution().select(identity, call, symbols) == []


def test_javascript_last_plain_method_wins_but_typescript_duplicates_do_not(
    selection_case,
):
    identity, call, symbols = selection_case(
        ["method_definition"] * 2, bodies=[True, True]
    )
    assert javascript.JavaScriptResolution().select(identity, call, symbols) == [
        symbols[1]
    ]
    assert typescript.TypeScriptResolution().select(identity, call, symbols) == []


@pytest.mark.parametrize("accessor", ["get", "set"])
def test_javascript_accessors_are_not_duplicate_method_implementations(
    selection_case, accessor
):
    identity, call, symbols = selection_case(
        ["method_definition"] * 2, bodies=[True, True]
    )
    cache = identity.syntax[call.file.source.path]
    old_node = cache.node
    cache.node = lambda start, end: (
        node("method_definition", children=[node(accessor)], body=node("block"))
        if start == 20
        else old_node(start, end)
    )
    assert javascript.JavaScriptResolution().select(identity, call, symbols) == []


@pytest.mark.parametrize(
    ("parameters", "arguments", "expected"),
    [
        ([], [], True),
        ([Parameter("x", None)], [], False),
        ([Parameter("x", None, default=True)], [], True),
        ([Parameter("xs", None, variadic=True)], [None, None, None], True),
        ([Parameter("x", None)], [None, None], False),
        ([Parameter("x", None), Parameter("y", None, default=True)], ["x"], True),
        ([Parameter("x", None)], ["unknown"], False),
        ([Parameter("x", None)], ["x", "x"], False),
        ([Parameter("x", None), Parameter("x", None)], ["x"], False),
    ],
)
def test_jvm_argument_assignment_requires_each_non_default_parameter(
    parameters, arguments, expected
):
    context = TypeContext(syntax(adapter=kotlin.KotlinResolution()), set())
    invocation = CallContext(context, context, node("function_declaration"))
    args = [Argument(node(), name) for name in arguments]
    assert accepts(invocation, parameters, args) is expected


def test_jvm_spread_preserves_unknown_arity_instead_of_rejecting_candidate():
    context = TypeContext(syntax(adapter=kotlin.KotlinResolution()), set())
    assert (
        accepts(
            CallContext(context, context, None), [], [Argument(node(), spread=True)]
        )
        is True
    )


@pytest.mark.parametrize(
    ("family", "actual", "expected_type", "rejected"),
    [
        ("java", "String", "int", True),
        ("java", "int", "long", False),
        ("java", "String", "java.lang.String", False),
        ("java", "int", "Number", False),
        ("java", None, "int", False),
        ("kotlin", "String", "Int", True),
        ("kotlin", "Int", "Byte", False),
        ("kotlin", "Int", "Long", False),
        ("kotlin", "Long", "Int", True),
        ("kotlin", "String", "String", False),
    ],
)
def test_jvm_type_filter_rejects_only_proven_closed_domain_mismatches(
    family, actual, expected_type, rejected
):
    assert incompatible(actual, expected_type, family) is rejected


@pytest.mark.parametrize(
    ("family", "annotation", "ambiguous", "imports", "raw", "expected"),
    [
        ("java", "int", {"int"}, ["external"], "?", "int"),
        ("java", "String", {"String"}, [], "", None),
        ("java", "String", set(), ["external"], "", None),
        ("kotlin", "String", set(), [], "String?", None),
        ("kotlin", "String", set(), [], "Box<String>", None),
        ("kotlin", "String", set(), [], "String", "String"),
    ],
)
def test_jvm_type_proof_preserves_shadowing_and_lossy_annotation_uncertainty(
    family, annotation, ambiguous, imports, raw, expected
):
    cache = syntax(
        adapter=SimpleNamespace(family=family),
        imports=imports,
        nodes=[node("user_type", raw, start=1, end=5)],
    )
    assert (
        proven_type(TypeContext(cache, ambiguous), annotation, node(start=0, end=10))
        == expected
    )


@pytest.mark.parametrize("adapter", [java.JavaResolution(), kotlin.KotlinResolution()])
def test_jvm_select_uses_arity_and_literal_types_without_parser(adapter):
    file = parsed(language=adapter.family)
    symbols = [symbol(start=start, language=adapter.family) for start in [10, 20, 30]]
    declarations = {}
    integer = "int" if adapter.family == "java" else "Int"
    for candidate, annotation, count in zip(
        symbols, ["String", integer, integer], [1, 1, 2]
    ):
        if adapter.family == "java":
            parameters = [
                node(
                    "formal_parameter",
                    name=node(value=f"p{i}"),
                    type=node("type_identifier", annotation),
                )
                for i in range(count)
            ]
            declaration = node(
                "method_declaration",
                parameters=node("formal_parameters", children=parameters),
            )
        else:
            parameters = [
                node(
                    "parameter",
                    children=[
                        node("simple_identifier", f"p{i}"),
                        node("user_type", annotation),
                    ],
                )
                for i in range(count)
            ]
            declaration = node(
                "function_declaration",
                children=[node("function_value_parameters", children=parameters)],
            )
        declarations[(candidate.start_byte, candidate.end_byte)] = declaration
    argument = node("string_literal", '"hello"')
    if adapter.family == "java":
        call = node(
            "method_invocation", arguments=node("argument_list", children=[argument])
        )
    else:
        call = node(
            "call_expression",
            children=[
                node(
                    "call_suffix",
                    children=[
                        node(
                            "value_arguments",
                            children=[node("value_argument", children=[argument])],
                        )
                    ],
                )
            ],
        )
    declarations[(50, 60)] = call
    cache = syntax(adapter=adapter, file=file, declarations=declarations)
    identity = SimpleNamespace(syntax={file.source.path: cache})
    assert adapter.select(identity, request(file), symbols) == [symbols[0]]


@pytest.mark.parametrize("adapter", [java.JavaResolution(), kotlin.KotlinResolution()])
def test_jvm_reference_has_no_arity_and_requires_sole_candidate(adapter):
    file = parsed()
    identity = SimpleNamespace(
        syntax={file.source.path: syntax(adapter=adapter, file=file)}
    )
    candidates = [symbol(start=10), symbol(start=20)]
    assert adapter.select(identity, request(file), candidates) == []
    assert adapter.select(identity, request(file), candidates[:1]) == candidates[:1]
    assert adapter.select(identity, request(file), []) == []


@pytest.mark.parametrize(
    ("count", "qualifier", "foreign", "expected"),
    [
        (0, None, False, []),
        (1, None, False, [0, 1]),
        (2, None, False, [0]),
        (3, None, False, []),
        (1, "Mod", False, [0]),
        (1, None, True, [0]),
    ],
)
def test_elixir_default_arity_and_private_visibility(
    count, qualifier, foreign, expected
):
    file = parsed(language="elixir")
    candidates = [
        symbol(start=10),
        symbol(start=20, path="other.ex" if foreign else file.source.path),
    ]
    call_node = node(
        "call", arguments=node("arguments", children=[node() for _ in range(count)])
    )
    identity = SimpleNamespace(
        syntax={file.source.path: syntax(declarations={(50, 60): call_node})},
        clauses={candidates[0].key: (1, 2, False), candidates[1].key: (1, 1, True)},
    )
    assert elixir.ElixirResolution().select(
        identity, request(file, qualifier=qualifier), candidates
    ) == [candidates[i] for i in expected]


def test_elixir_pipeline_supplies_one_argument_and_keeps_same_function_clauses():
    file = parsed(language="elixir")
    call_node = node("identifier", "run")
    node("binary_operator", "value |> run", right=call_node)
    candidates = [symbol(start=10), symbol(start=20)]
    identity = SimpleNamespace(
        syntax={file.source.path: syntax(declarations={(50, 60): call_node})},
        clauses={s.key: (1, 1, False) for s in candidates},
    )
    assert (
        elixir.ElixirResolution().select(identity, request(file), candidates)
        == candidates
    )
    candidates[1].parent_key = "other-module"
    assert elixir.ElixirResolution().select(identity, request(file), candidates) == []


def test_python_overload_requires_real_typing_provider_and_final_implementation(
    selection_case,
):
    adapter = python.PythonResolution()
    identity, call, candidates = selection_case(
        ["function_definition"] * 2, adapter=adapter
    )
    cache = identity.syntax[call.file.source.path]
    provider = node(
        "import_from_statement",
        start=0,
        module_name=node(value="typing"),
        name=[node(value="overload")],
    )
    declaration = cache.node(10, 20)
    node("decorated_definition", children=[node("decorator", "@overload"), declaration])
    cache.nodes = [provider]
    cache.scope = lambda imported: node("module")
    assert adapter.select(identity, call, candidates) == [candidates[1]]
    assert adapter.select(identity, call, candidates[:1]) == []
    cache.shadowed = lambda name, position: True
    assert adapter.select(identity, call, candidates) == []
