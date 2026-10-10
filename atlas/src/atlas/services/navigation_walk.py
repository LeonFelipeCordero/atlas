"""Deterministic bounded graph traversal; no storage-specific types."""

from collections import deque
from dataclasses import dataclass, field

from atlas.domain.navigation import NavigationReader, Record


@dataclass(frozen=True)
class Expansion:
    direction: str
    relations: list[str]
    max_nodes: int
    max_edges: int


@dataclass
class Walk:
    nodes: dict[str, Record] = field(default_factory=dict)
    edges: dict[int, Record] = field(default_factory=dict)
    parents: dict[str, tuple[str, int]] = field(default_factory=dict)
    cutoffs: dict[str, str] = field(default_factory=dict)
    external: set[str] = field(default_factory=set)

    def output(self) -> Record:
        return {
            "nodes": list(self.nodes.values()), "edges": list(self.edges.values()),
            "boundaries": [{"stableKey": key, "reason": reason, "expandable": True} for key, reason in self.cutoffs.items()]
            + [{"stableKey": key, "reason": "external_unresolved_or_ambiguous", "expandable": False} for key in sorted(self.external)],
            "truncated": bool(self.cutoffs),
        }


def traverse(reader: NavigationReader, key: str, direction: str, relations: list[str], depth: int, max_nodes: int, max_edges: int) -> Walk:
    walk = Walk(nodes={key: reader.node(key)})
    options = Expansion(direction, relations, max_nodes, max_edges)
    frontier = deque([(key, 0)])
    while frontier:
        current, distance = frontier.popleft()
        if walk.nodes[current]["external"]:
            walk.external.add(current)
            continue
        if distance >= depth:
            walk.cutoffs[current] = "depth"
            continue
        expand(reader, walk, frontier, current, distance, options)
    return walk


def expand(reader: NavigationReader, walk: Walk, frontier: deque[tuple[str, int]], key: str, distance: int, options: Expansion) -> None:
    remaining = options.max_edges - len(walk.edges)
    rows = reader.edges(key, options.direction, options.relations, remaining + 1)
    for edge in rows:
        if edge["ordinal"] in walk.edges:
            continue
        if len(walk.edges) >= options.max_edges:
            walk.cutoffs[key] = "maxEdges"
            break
        add_edge(reader, walk, frontier, key, distance, edge, options.max_nodes)
    if len(rows) > remaining:
        walk.cutoffs.setdefault(key, "edgeFetchLimit")


def add_edge(reader: NavigationReader, walk: Walk, frontier: deque[tuple[str, int]], key: str, distance: int, edge: Record, max_nodes: int) -> None:
    neighbor = edge["targetStableKey"] if edge["sourceStableKey"] == key else edge["sourceStableKey"]
    if neighbor not in walk.nodes:
        if len(walk.nodes) >= max_nodes:
            walk.cutoffs[key] = "maxNodes"
            return
        walk.nodes[neighbor] = reader.node(neighbor)
        walk.parents[neighbor] = (key, edge["ordinal"])
        frontier.append((neighbor, distance + 1))
    walk.edges[edge["ordinal"]] = edge


def route(walk: Walk, start: str, target: str) -> Record:
    if target not in walk.nodes:
        return {"status": "unknown" if walk.cutoffs else "not_found", "path": [], "pathEdges": []}
    keys = [target]
    edges: list[Record] = []
    while keys[-1] != start:
        parent, ordinal = walk.parents[keys[-1]]
        keys.append(parent)
        edges.append(walk.edges[ordinal])
    return {"status": "found", "path": list(reversed(keys)), "pathEdges": list(reversed(edges))}
