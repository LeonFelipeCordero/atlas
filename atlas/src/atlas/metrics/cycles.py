"""Detect deterministic circular dependency groups in file-level imports.

Symbol imports are projected to owning files; external and type-only imports are excluded.
Iterative strongly connected component traversal avoids recursion and exhaustive
cycle enumeration. Each group includes one representative closed cycle.
"""

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from typing_extensions import TypedDict


class CircularGroup(TypedDict):
    """Cyclic file component with a membership-derived ID and projected imports."""

    id: str
    nodeStableKeys: list[str]
    exampleCycle: list[str]
    edges: list[dict[str, object]]


class CircularDependencies(TypedDict):
    """Versioned cycle report; an empty groups list means no import cycles."""

    version: int
    groups: list[CircularGroup]


def _owner_boundary(
    key: str, node: dict[str, object], owners: dict[str, str | None]
) -> tuple[bool, str | None]:
    if key in owners:
        return True, owners[key]
    if node.get("type") == "external" or node.get("level") == "external":
        return True, None
    if node.get("type") == "file":
        return True, key
    return False, None


def _find_file_owner(
    key: str, by_key: dict[str, dict[str, object]], owners: dict[str, str | None]
) -> tuple[str | None, set[str]]:
    trail: set[str] = set()
    current = key
    owner = None
    while current in by_key and current not in trail:
        node = by_key[current]
        terminal, owner = _owner_boundary(current, node, owners)
        if terminal:
            break
        trail.add(current)
        current = str(node.get("parentStableKey"))
    return owner, trail


def _file_owners(nodes: list[dict[str, object]]) -> dict[str, str | None]:
    by_key = {str(node["stableKey"]): node for node in nodes}
    owners: dict[str, str | None] = {}
    for key in sorted(by_key):
        owner, trail = _find_file_owner(key, by_key, owners)
        owners[key] = owner
        owners.update(dict.fromkeys(trail, owner))
    return owners


def _import_edges(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> list[dict[str, object]]:
    owners = _file_owners(nodes)
    projected = []
    for edge in edges:
        projection = _project_import(edge, owners)
        if projection is not None:
            projected.append(projection)
    return sorted(projected, key=lambda edge: json.dumps(edge, sort_keys=True))


def _import_metadata(edge: dict[str, object]) -> dict[str, object]:
    return {
        key: edge[key]
        for key in ("path", "line", "evidence", "confidence", "type")
        if key in edge
    }


def _project_import(
    edge: dict[str, object], owners: dict[str, str | None]
) -> dict[str, object] | None:
    if edge.get("type") != "IMPORTS" or edge.get("typeOnly") is True:
        return None
    source = str(edge["sourceStableKey"])
    target = str(edge["targetStableKey"])
    source_file, target_file = owners.get(source), owners.get(target)
    if source_file is None or target_file is None:
        return None
    # Only a direct file -> same file import is a genuine self dependency.
    if source_file == target_file and (source != source_file or target != target_file):
        return None
    return {
        "sourceStableKey": source_file,
        "targetStableKey": target_file,
        **_import_metadata(edge),
    }


def _reverse_group(
    root: str, reverse: dict[str, list[str]], visited: set[str]
) -> list[str]:
    pending = [root]
    group = []
    while pending:
        node = pending.pop()
        group.append(node)
        _enqueue_unvisited(reverse[node], visited, pending)
    return sorted(group)


def _enqueue_unvisited(
    targets: list[str], visited: set[str], pending: list[str]
) -> None:
    for target in targets:
        if target not in visited:
            visited.add(target)
            pending.append(target)


def _finish_from(
    root: str, adjacency: dict[str, list[str]], visited: set[str]
) -> list[str]:
    finished = []
    stack = [(root, iter(adjacency[root]))]
    while stack:
        node, targets = stack[-1]
        target = next(targets, None)
        if target is None:
            finished.append(node)
            stack.pop()
        elif target not in visited:
            visited.add(target)
            stack.append((target, iter(adjacency[target])))
    return finished


def _add_reverse_edges(
    source: str, targets: list[str], reverse: dict[str, list[str]]
) -> None:
    for target in targets:
        reverse[target].append(source)


def _reverse_adjacency(adjacency: dict[str, list[str]]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {key: [] for key in adjacency}
    for source, targets in adjacency.items():
        _add_reverse_edges(source, targets, reverse)
    return reverse


def _finish_order(adjacency: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    finished = []
    for root in adjacency:
        if root in visited:
            continue
        visited.add(root)
        finished.extend(_finish_from(root, adjacency, visited))
    return finished


def strongly_connected_components(adjacency: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Kosaraju; all components in source-first topological order.

    Adjacency must include every target as a key. Traversal takes O(V + E),
    excluding sorting members within each component. No recursion is used.
    Return sorted members in each component, including isolated vertices.
    Missing target keys raise KeyError; the adjacency is not modified.
    """
    reverse = _reverse_adjacency(adjacency)
    visited: set[str] = set()
    result = []
    for root in reversed(_finish_order(adjacency)):
        if root in visited:
            continue
        visited.add(root)
        group = _reverse_group(root, reverse, visited)
        result.append(group)
    return result


def _components(adjacency: dict[str, list[str]]) -> list[list[str]]:
    return sorted(
        group
        for group in strongly_connected_components(adjacency)
        if len(group) > 1 or group[0] in adjacency[group[0]]
    )


def _path_to_start(start: str, parents: dict[str, str | None]) -> list[str]:
    path = [start]
    current = parents[start]
    while current is not None:
        path.append(current)
        current = parents[current]
    return [start, *reversed(path)]


@dataclass
class _CycleSearch:
    adjacency: dict[str, list[str]]
    members: set[str]
    start: str
    parents: dict[str, str | None]
    pending: deque[str]

    def visit_neighbors(self, node: str) -> bool:
        """Record unseen in-group neighbors and queue those not closing the cycle.

        Return True as soon as a neighbor reaches start; update parents in place.
        """
        for target in self.adjacency[node]:
            if target not in self.members or target in self.parents:
                continue
            self.parents[target] = node
            if target == self.start:
                return True
            self.pending.append(target)
        return False


def _example_cycle(group: list[str], adjacency: dict[str, list[str]]) -> list[str]:
    if len(group) == 1:
        return [group[0], group[0]]
    members = set(group)
    start = group[0]
    first = next(
        target for target in adjacency[start] if target in members and target != start
    )
    search = _CycleSearch(adjacency, members, start, {first: None}, deque([first]))
    while search.pending:
        node = search.pending.popleft()
        if search.visit_neighbors(node):
            return _path_to_start(start, search.parents)
    raise ValueError("Strongly connected component has no return path")


def _cycle_group(keys: list[str], adjacency: dict[str, list[str]]) -> CircularGroup:
    digest = hashlib.sha256(json.dumps(keys, ensure_ascii=True).encode()).hexdigest()
    return {
        "id": f"import-cycle:{digest}",
        "nodeStableKeys": keys,
        "exampleCycle": _example_cycle(keys, adjacency),
        "edges": [],
    }


def _register_members(group: CircularGroup, membership: dict[str, CircularGroup]) -> None:
    for key in group["nodeStableKeys"]:
        membership[key] = group


def circular_dependencies(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> CircularDependencies:
    """Find cyclic file-import components without modifying the input graph.

    Use on graph nodes and edges to report sorted groups with stable SHA-256 IDs,
    sorted members, one closed example cycle, and internal projected imports.
    Direct file self-imports count; imports within a file's symbols and explicitly
    type-only imports do not.

    Args:
        nodes: Nodes with stableKey and type; parents identify symbol owners.
        edges: Relationships; IMPORTS edges require source/target stable keys.
    Returns:
        Version-1 report, including an empty groups list for acyclic graphs.
    Raises:
        KeyError: A node lacks stableKey or an import lacks an endpoint key.
        TypeError: Copied import metadata is not JSON-serializable for sorting.

    Examples:
        >>> circular_dependencies([], [])
        {'version': 1, 'groups': []}
        >>> nodes = [{"stableKey": "file:a.py", "type": "file"}]
        >>> edges = [{"type": "IMPORTS", "sourceStableKey": "file:a.py", "targetStableKey": "file:a.py"}]
        >>> circular_dependencies(nodes, edges)["groups"][0]["exampleCycle"]
        ['file:a.py', 'file:a.py']
    """
    projected = _import_edges(nodes, edges)
    neighbors: dict[str, set[str]] = {}
    for edge in projected:
        source, target = str(edge["sourceStableKey"]), str(edge["targetStableKey"])
        neighbors.setdefault(source, set()).add(target)
        neighbors.setdefault(target, set())
    adjacency = {key: sorted(neighbors[key]) for key in sorted(neighbors)}
    groups: list[CircularGroup] = []
    membership: dict[str, CircularGroup] = {}
    for keys in _components(adjacency):
        group = _cycle_group(keys, adjacency)
        groups.append(group)
        _register_members(group, membership)
    for edge in projected:
        source_group = membership.get(str(edge["sourceStableKey"]))
        if (
            source_group is not None
            and membership.get(str(edge["targetStableKey"])) is source_group
        ):
            source_group["edges"].append(edge)
    return {"version": 1, "groups": groups}
