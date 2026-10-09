"""Calculate complexity by traversing normalized adapter decision/scope facts."""

from collections.abc import Iterator

from tree_sitter import Node

from .adapters import DEFAULT_METRICS
from .adapters.base import MetricPolicy


from ..domain.models import Complexity


def _decision_metrics(
    node: Node, depth: int, loop_depth: int, policy: MetricPolicy
) -> tuple[int, int, int, int]:
    if policy.alternative(node):
        depth = max(0, depth - 1)
    decision = policy.decision(node)
    depth += int(decision)
    return (
        int(decision) + int(policy.logical(node)),
        int(decision and depth > 2),
        int(node.type in policy.loops and loop_depth > 0),
        depth,
    )


def _child_frames(
    node: Node, depth: int, loop_depth: int
) -> Iterator[tuple[Node, int, int]]:
    for child in reversed(node.named_children):
        yield child, depth, loop_depth


def calculate_complexity(
    root: Node, policy: MetricPolicy = DEFAULT_METRICS
) -> Complexity:
    """Count entry/decisions, penalties below depth two, and nested loops.

    Pass an adapter's policy when the language is known. The default retains the
    node-only API across language-pack grammars. Nested callable/type bodies are
    excluded; alternatives share their preceding decision's depth.
    """
    root = policy.body(root)
    base, nested, loops, maximum = 1, 0, 0, 0
    stack = [(root, 0, 0)]
    while stack:
        node, depth, loop_depth = stack.pop()
        if node != root and policy.scope(node):
            continue
        decisions, penalty, nested_loops, depth = _decision_metrics(
            node, depth, loop_depth, policy
        )
        base += decisions
        nested += penalty
        loops += nested_loops
        maximum = max(maximum, depth)
        child_loop_depth = loop_depth + int(node.type in policy.loops)
        stack.extend(_child_frames(node, depth, child_loop_depth))
    return Complexity(base, nested, loops, base + nested + loops, maximum)
