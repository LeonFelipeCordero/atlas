"""Elixir clauses, defaults, guards, and module bindings from stub syntax."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters import elixir
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


@pytest.mark.parametrize(
    "case",
    [
        ("case", ["_"], False, False),
        ("case", ["value"], False, True),
        ("case", ["_", "_"], False, True),
        ("case", ["_"], True, True),
        ("case", ["true"], False, True),
        ("cond", ["true"], False, False),
        ("cond", ["false"], False, True),
        ("anonymous_function", ["value"], False, False),
        (None, ["value"], False, False),
    ],
)
def test_elixir_clause_decisions_preserve_guard_and_cond_semantics(
    case,
):
    owner, patterns, guarded, expected = case
    inputs = node("arguments", children=[node(value=value) for value in patterns])
    left = node("binary_operator", left=inputs) if guarded else inputs
    clause = node("stab_clause", left=left)
    if owner == "anonymous_function":
        node(owner, children=[clause])
    elif owner:
        block = node("do_block", children=[clause])
        node("call", target=node(value=owner), children=[block])
    assert elixir.clause_decision(clause) is expected


@pytest.mark.parametrize(
    "name", ["def", "defp", "defmodule", "if", "unless", "cond", "run"]
)
def test_elixir_scope_and_decision_classification(name):
    expression = node("call", target=node(value=name))
    assert (elixir.scope(expression), elixir.call_decision(expression)) == (
        name in elixir.SCOPES,
        name in {"if", "unless"},
    )


@pytest.mark.parametrize("guarded", [True, False])
def test_elixir_guard_token_is_a_decision(guarded):
    expression = node("binary_operator", children=[node("when" if guarded else "+")])
    assert elixir.guard_decision(expression) is guarded


@pytest.mark.parametrize(
    "head_kind", ["identifier", "call", "integer", "missing", "error"]
)
def test_elixir_declaration_parameter_extraction(head_kind):
    head = node(
        head_kind,
        "run",
        arguments=node("arguments", children=[node(value="x"), node(value="y")]),
        error=head_kind == "error",
    )
    declaration = node(
        "call",
        target=node(value="def"),
        arguments=node("arguments", children=[] if head_kind == "missing" else [head]),
    )
    assert elixir.parameter_count(declaration) == {"identifier": 0, "call": 2}.get(
        head_kind
    )


@pytest.mark.parametrize("shape", ["empty", "guarded", "invalid"])
def test_elixir_anonymous_clause_inputs(shape):
    inputs = node("arguments", children=[node(value="x")])
    left = (
        node("binary_operator", left=inputs)
        if shape == "guarded"
        else node("identifier")
    )
    clause = node("stab_clause", **({} if shape == "empty" else {"left": left}))
    assert (
        elixir.parameter_count(node("anonymous_function", children=[clause]))
        == {"empty": 0, "guarded": 1, "invalid": None}[shape]
    )


@pytest.mark.parametrize("private", [True, False])
@pytest.mark.parametrize("guarded", [True, False])
def test_elixir_clause_index_records_default_arity_and_private_flag(private, guarded):
    declaration = symbol("run", language="elixir", path="lib.ex")
    ignored = symbol("Mod", language="elixir", kind="module", path="lib.ex")
    foreign = symbol("other", language="python")
    head = node(
        "call",
        arguments=node(
            "arguments",
            children=[node(value="required"), node(value="optional \\\\ 1")],
        ),
    )
    if guarded:
        head = node("binary_operator", left=head)
    definition = node(
        "call",
        target=node(value="defp" if private else "def"),
        arguments=node("arguments", children=[head]),
    )
    file = parsed("lib.ex", "elixir", symbols=[declaration, ignored, foreign])
    state = syntax(declarations={(10, 20): definition})
    assert elixir.ElixirResolution().clauses(
        ParsedRepository([file]), {"lib.ex": state}
    ) == {declaration.key: (1, 2, private)}


@pytest.mark.parametrize("pipeline", [True, False])
@pytest.mark.parametrize("identifier", [True, False])
def test_elixir_selection_handles_zero_argument_pipeline_identifiers(
    pipeline, identifier
):
    file = parsed("lib.ex", "elixir")
    candidate = symbol("run", language="elixir", path="lib.ex")
    expression = node("identifier" if identifier else "call", "run")
    if pipeline:
        node("binary_operator", "value |> run", right=expression)
    identity = SimpleNamespace(
        syntax={"lib.ex": syntax(declarations={(50, 60): expression})},
        clauses={candidate.key: (1, 1, False)},
    )
    assert elixir.ElixirResolution().select(identity, request(file), [candidate]) == (
        [candidate] if pipeline or identifier else []
    )


@pytest.mark.parametrize("kind", ["module", "function"])
def test_elixir_module_identity_uses_module_name_or_terminal_qualified_name(kind):
    declaration = symbol("Outer.Inner", kind=kind, qualified_name="Outer::Inner")
    assert elixir.ElixirResolution().module_identity(
        parsed(), declaration, syntax()
    ) == ("Outer.Inner" if kind == "module" else "Inner")


@pytest.mark.parametrize("name", ["alias", "import", "require", "run"])
def test_elixir_import_nodes_exclude_nonbinding_directives(name):
    assert elixir.ElixirResolution().is_import_node(
        node("call", target=node(value=name))
    ) is (name in {"alias", "import"})
