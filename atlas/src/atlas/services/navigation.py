"""Agent-facing graph navigation orchestration over a private domain read port."""

from atlas.domain.navigation import NavigationReader, Record
from atlas.services.navigation_source import source_excerpt
from atlas.services.navigation_walk import route, traverse


class NavigationService:
    def __init__(self, reader: NavigationReader) -> None:
        self._reader = reader

    def response(self, payload: Record, filters: Record, nodes: list[Record]) -> Record:
        paths = sorted({node["path"] for node in nodes if node.get("path")})
        diagnostics = self._reader.diagnostics(paths, 31) if paths else []
        return {**self._reader.snapshot.metadata(), "filters": filters, **payload,
                "diagnostics": diagnostics[:30], "diagnosticsTruncated": len(diagnostics) > 30}

    def overview(self) -> Record:
        payload = self._reader.overview()
        return self.response(payload, {"rootLimit": 30}, payload["roots"])

    def find(self, query: str, limit: int) -> Record:
        rows = self._reader.find(query, limit + 1)
        return self.response({"nodes": rows[:limit], "truncated": len(rows) > limit}, {"query": query, "limit": limit}, rows[:limit])

    def show(self, key: str) -> Record:
        node = self._reader.node(key)
        ancestors, truncated = self.ancestors(node)
        return self.response({"node": node, "ancestors": ancestors, "truncated": truncated}, {"key": key, "ancestorLimit": 100}, [node, *ancestors])

    def ancestors(self, node: Record) -> tuple[list[Record], bool]:
        ancestors: list[Record] = []
        seen = {node["stableKey"]}
        parent = node["parentStableKey"]
        while parent is not None and parent not in seen and len(ancestors) < 100:
            seen.add(parent)
            ancestor = self._reader.node(parent)
            ancestors.append(ancestor)
            parent = ancestor["parentStableKey"]
        return ancestors, parent is not None

    def children(self, key: str, limit: int, offset: int) -> Record:
        node = self._reader.node(key)
        rows = self._reader.children(key, limit + 1, offset)
        truncated = len(rows) > limit
        return self.response({"nodes": rows[:limit], "truncated": truncated, "nextOffset": offset + limit if truncated else None},
                             {"key": key, "limit": limit, "offset": offset}, [node, *rows[:limit]])

    def context(self, key: str, direction: str, relations: list[str], depth: int, max_nodes: int, max_edges: int) -> Record:
        walk = traverse(self._reader, key, direction, relations, depth, max_nodes, max_edges)
        filters = {"key": key, "direction": direction, "relations": relations, "depth": depth, "maxNodes": max_nodes, "maxEdges": max_edges}
        return self.response(walk.output(), filters, list(walk.nodes.values()))

    def path(self, start: str, target: str, direction: str, relations: list[str], max_depth: int, max_nodes: int, max_edges: int) -> Record:
        self._reader.node(target)
        walk = traverse(self._reader, start, direction, relations, max_depth, max_nodes, max_edges)
        filters = {"from": start, "to": target, "direction": direction, "relations": relations, "maxDepth": max_depth, "maxNodes": max_nodes, "maxEdges": max_edges}
        return self.response({**walk.output(), **route(walk, start, target)}, filters, list(walk.nodes.values()))

    def source(self, key: str, max_lines: int, start_line: int | None) -> Record:
        node = self._reader.node(key)
        payload = source_excerpt(self._reader, node, max_lines, start_line)
        return self.response({"source": payload}, {"key": key, "maxLines": max_lines, "startLine": start_line}, [node])
