"""Calculate complexity by traversing normalized adapter decision/scope facts."""

from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node

from .adapters import DEFAULT_METRICS
from .adapters.base import MetricPolicy


from ..domain.models import Complexity


@dataclass(frozen=True)
class _TraversalFrame:
    node: Node
    decision_depth: int
    loop_depth: int


def _decision_metrics(
    frame: _TraversalFrame, policy: MetricPolicy
) -> tuple[int, int, int, int]:
    node, depth, loop_depth = frame.node, frame.decision_depth, frame.loop_depth
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
) -> Iterator[_TraversalFrame]:
    for child in reversed(node.named_children):
        yield _TraversalFrame(child, depth, loop_depth)


def calculate_complexity(
    root: Node, policy: MetricPolicy = DEFAULT_METRICS
) -> Complexity:
    """Count entry/decisions, penalties below depth two, and nested loops.

    Pass an adapter's policy when the language is known. The default retains the
    node-only API across language-pack grammars. Nested callable/type bodies are
    excluded; alternatives share their preceding decision's depth. Return base
    complexity (entry, decisions, logical operators), nested-decision penalties,
    nested-loop count, their weighted sum, and maximum decision depth.
    """
    root = policy.body(root)
    base, nested, loops, maximum = 1, 0, 0, 0
    stack = [_TraversalFrame(root, 0, 0)]
    while stack:
        frame = stack.pop()
        node, loop_depth = frame.node, frame.loop_depth
        if node != root and policy.scope(node):
            continue
        decisions, penalty, nested_loops, depth = _decision_metrics(
            frame, policy
        )
        base += decisions
        nested += penalty
        loops += nested_loops
        maximum = max(maximum, depth)
        child_loop_depth = loop_depth + int(node.type in policy.loops)
        stack.extend(_child_frames(node, depth, child_loop_depth))
    return Complexity(base, nested, loops, base + nested + loops, maximum)
