"""Distinct dependency peers and reverse reachability for internal level views."""

from collections import Counter
from itertools import chain

from .cycles import strongly_connected_components
from ..domain.models import GraphView

METRIC_NAMES = ("fanIn", "fanOut", "transitiveChangeImpact")


def _adjacency(view: GraphView) -> dict[str, list[str]]:
    neighbors: dict[str, set[str]] = {key: set() for key in view["nodes"]}
    for edge in view["edges"]:
        source, target = edge["sourceStableKey"], edge["targetStableKey"]
        if source in neighbors and target in neighbors and source != target:
            neighbors[source].add(target)
    return {key: sorted(targets) for key, targets in neighbors.items()}


def _component_targets(
    groups: list[list[str]], adjacency: dict[str, list[str]]
) -> list[set[int]]:
    membership = {key: index for index, group in enumerate(groups) for key in group}
    return [
        {
            membership[target]
            for source in group
            for target in adjacency[source]
            if membership[target] != index
        }
        for index, group in enumerate(groups)
    ]


def _propagate(reachable: int, targets: set[int], pending: dict[int, int]) -> None:
    for target in targets:
        pending[target] = pending.get(target, 0) | reachable


def _change_impact(adjacency: dict[str, list[str]]) -> dict[str, int]:
    groups = strongly_connected_components(adjacency)
    targets = _component_targets(groups, adjacency)
    pending: dict[int, int] = {}
    impact: dict[str, int] = {}
    offset = 0
    for index, group in enumerate(groups):
        # One bit per original node makes SCC sizes and diamond deduplication exact.
        reachable = pending.pop(index, 0) | (((1 << len(group)) - 1) << offset)
        offset += len(group)
        count = reachable.bit_count() - 1
        impact.update(dict.fromkeys(group, count))
        _propagate(reachable, targets[index], pending)
    return impact


def dependency_metrics(view: GraphView) -> dict[str, dict[str, int | float | None]]:
    """Count peers and instability in a DEPENDS_ON projection, including isolated nodes.

    Edges point from dependent to dependency. All relationship kinds (including
    type-only imports) are already aggregated by the artifact's internal view.
    SCC condensation handles cycles iteratively. Bitsets are propagated in
    topological order and discarded after propagation, rather than retaining an
    all-pairs closure. A long chain thus needs only one live reachability bitset.
    """
    adjacency = _adjacency(view)
    fan_in = Counter(chain.from_iterable(adjacency.values()))
    impact = _change_impact(adjacency)
    return {
        key: {
            "fanIn": fan_in[key],
            "fanOut": len(targets),
            "transitiveChangeImpact": impact[key],
            "instability": (
                len(targets) / (fan_in[key] + len(targets))
                if targets or fan_in[key] else None
            ),
        }
        for key, targets in adjacency.items()
    }
