"""Deterministic bounded graph traversal; no storage-specific types."""

from collections import deque
from dataclasses import dataclass, field

from atlas.domain.navigation import EdgeRequest, NavigationReader, Record, TraversalRequest


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


class Traversal:
    def __init__(self, reader: NavigationReader, request: TraversalRequest) -> None:
        self._reader = reader
        self.request = request
        self.walk = Walk(nodes={request.key: reader.node(request.key)})
        self.frontier = deque([(request.key, 0)])

    def run(self) -> Walk:
        while self.frontier:
            current, distance = self.frontier.popleft()
            if self.walk.nodes[current]["external"]:
                self.walk.external.add(current)
                continue
            if distance >= self.request.depth:
                self.walk.cutoffs[current] = "depth"
                continue
            self.expand(current, distance)
        return self.walk

    def expand(self, key: str, distance: int) -> None:
        remaining = self.request.max_edges - len(self.walk.edges)
        rows = self._reader.edges(EdgeRequest(key, self.request.direction, self.request.relations, remaining + 1))
        for edge in rows:
            if edge["ordinal"] in self.walk.edges:
                continue
            if len(self.walk.edges) >= self.request.max_edges:
                self.walk.cutoffs[key] = "maxEdges"
                break
            self.add_edge((key, distance), edge)
        if len(rows) > remaining:
            self.walk.cutoffs.setdefault(key, "edgeFetchLimit")

    def add_edge(self, position: tuple[str, int], edge: Record) -> None:
        key, distance = position
        neighbor = edge["targetStableKey"] if edge["sourceStableKey"] == key else edge["sourceStableKey"]
        if neighbor not in self.walk.nodes:
            if len(self.walk.nodes) >= self.request.max_nodes:
                self.walk.cutoffs[key] = "maxNodes"
                return
            self.walk.nodes[neighbor] = self._reader.node(neighbor)
            self.walk.parents[neighbor] = (key, edge["ordinal"])
            self.frontier.append((neighbor, distance + 1))
        self.walk.edges[edge["ordinal"]] = edge


def traverse(reader: NavigationReader, request: TraversalRequest) -> Walk:
    return Traversal(reader, request).run()


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
