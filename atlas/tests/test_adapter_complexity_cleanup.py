"""Regression guards for the five refactored language policies."""

from tests.resolution_snapshot_support import fixture_bytes
from pathlib import Path
import pytest
from tree_sitter import Node
from tree_sitter_language_pack import get_parser
from atlas.metrics.adapters.elixir import _call_arity, _clause_signature
from atlas.metrics.adapters.python import irrefutable_pattern
from atlas.metrics.complexity import calculate_complexity


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


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("python-irrefutable-patterns-python-01", True),
        ("python-irrefutable-patterns-python-02", True),
        ("python-irrefutable-patterns-python-03", False),
        ("python-irrefutable-patterns-python-04", True),
        ("python-irrefutable-patterns-python-05", False),
        ("python-irrefutable-patterns-python-06", True),
        ("python-irrefutable-patterns-python-07", False),
        ("python-irrefutable-patterns-python-08", True),
        ("python-irrefutable-patterns-python-09", False),
    ],
)
def test_python_irrefutable_patterns(pattern, expected):
    root = (
        get_parser("python")
        .parse(
            fixture_bytes(
                "adapter_complexity_cleanup:test_python_irrefutable_patterns:54-11",
                pattern=pattern,
            )
        )
        .root_node
    )
    case = next((node for node in nodes(root) if node.type == "case_pattern"))
    assert irrefutable_pattern(case) is expected


def test_elixir_default_guard_and_pipeline_arities():
    root = (
        get_parser("elixir")
        .parse(
            fixture_bytes(
                "adapter_complexity_cleanup:test_elixir_default_guard_and_pipeline_arities:65-11"
            )
        )
        .root_node
    )
    assert not root.has_error
    calls = {node_text(node): node for node in nodes(root) if node.type == "call"}
    declaration = root.named_children[0]
    assert _clause_signature(declaration) == (1, 2, True)
    assert _call_arity(calls["next(extra)"]) == 2
    finish = next((node for node in nodes(root) if node.text == b"finish"))
    assert _call_arity(finish) == 1
    assert _clause_signature(None) == (0, 0, False)
    assert _call_arity(None) is None
