"""Regression guards for the five refactored language policies."""

from pathlib import Path
import pytest
from tree_sitter import Node
from tree_sitter_language_pack import get_parser
from atlas.metrics.adapters.elixir import _call_arity, _clause_signature
from atlas.metrics.adapters.python import irrefutable_pattern
from atlas.metrics.complexity import calculate_complexity
from tests.coffee_fixture import coffee_sources


def nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.named_children))


def node_text(node: Node) -> str:
    text = node.text
    assert text is not None
    return text.decode()


@pytest.mark.parametrize("phase", ["parsing", "metrics"])
@pytest.mark.parametrize("adapter", ["base", "elixir", "go", "kotlin", "python"])
def test_adapter_callable_complexity_budget(phase, adapter):
    path = (
        Path(__file__).parents[1]
        / "src"
        / "atlas"
        / phase
        / "adapters"
        / f"{adapter}.py"
    )
    root = get_parser("python").parse(path.read_bytes()).root_node
    assert not root.has_error
    for node in nodes(root):
        if node.type != "function_definition":
            continue
        metrics = calculate_complexity(node)
        name = node.child_by_field_name("name")
        assert name is not None
        label = node_text(name)
        assert metrics.cyclomaticComplexity <= 8, label
        assert metrics.loopNestedComplexity == 0, label
        assert metrics.maxDecisionDepth <= 3, label
        assert node.end_point.row - node.start_point.row < 100, label


@pytest.mark.parametrize("pattern,expected", [
    ("_", True), ("remaining", True), ("1", False), ("(assigned)", True),
    ("(drink,)", False), ("1 | _", True), ("1 as first", False),
    ("_ as ticket", True), ("OrderStatus.QUEUED", False),
])
def test_python_irrefutable_patterns(pattern, expected):
    source = next(source for source in coffee_sources("python")
                  if source.path.endswith("/scheduling.py"))
    root = get_parser("python").parse(source.source).root_node
    assert not root.has_error
    cases = [node for node in nodes(root)
             if node.type == "case_pattern" and node_text(node) == pattern]
    assert cases, pattern
    assert all(irrefutable_pattern(case) is expected for case in cases)


def elixir_scheduling_calls():
    source = next(source for source in coffee_sources("elixir")
                  if source.path == "brewing/scheduling.ex")
    root = get_parser("elixir").parse(source.source).root_node
    assert not root.has_error
    return {node_text(node): node for node in nodes(root) if node.type == "call"}


def test_elixir_default_guard_and_pipeline_arities():
    calls = elixir_scheduling_calls()
    declaration = next(node for node in calls.values()
                       if node_text(node).startswith("defp plan("))
    assert _clause_signature(declaration) == (1, 2, True)
    assert _call_arity(calls["prepare(multiplier)"]) == 2
    dispatch = next(node for node in nodes(declaration) if node.text == b"dispatch")
    assert _call_arity(dispatch) == 1
    assert _clause_signature(None) == (0, 0, False)
    assert _call_arity(None) is None
