"""Agent-facing graph navigation orchestration over a private domain read port."""

from atlas.domain.navigation import NavigationReader, PathRequest, Record, SourceOptions, TraversalRequest
from atlas.services.navigation_source import source_excerpt
from atlas.services.navigation_walk import route, traverse


class NavigationService:
    def __init__(self, reader: NavigationReader) -> None:
        self._reader = reader

    def response(self, payload: Record, filters: Record, nodes: list[Record]) -> Record:
        """Attach snapshot metadata, filters, and up to 30 diagnostics for node paths."""
        paths = sorted({node["path"] for node in nodes if node.get("path")})
        diagnostics = self._reader.diagnostics(paths, 31) if paths else []
        return {**self._reader.snapshot.metadata(), "filters": filters, **payload,
                "diagnostics": diagnostics[:30], "diagnosticsTruncated": len(diagnostics) > 30}

    def overview(self) -> Record:
        """Return graph counts and bounded roots with snapshot metadata/diagnostics."""
        payload = self._reader.overview()
        return self.response(payload, {"rootLimit": 30}, payload["roots"])

    def find(self, query: str, limit: int) -> Record:
        """Return ranked node matches with metadata and a lookahead truncation flag."""
        rows = self._reader.find(query, limit + 1)
        return self.response({"nodes": rows[:limit], "truncated": len(rows) > limit}, {"query": query, "limit": limit}, rows[:limit])

    def show(self, key: str) -> Record:
        """Return node details and bounded ancestors; missing keys raise NavigationError."""
        node = self._reader.node(key)
        ancestors, truncated = self.ancestors(node)
        return self.response({"node": node, "ancestors": ancestors, "truncated": truncated}, {"key": key, "ancestorLimit": 100}, [node, *ancestors])

    def ancestors(self, node: Record) -> tuple[list[Record], bool]:
        """Return nearest-first parents and whether a cycle/100-parent cap stopped us.

        Missing parent records propagate the reader's NavigationError.
        """
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
        """Return a child page with nextOffset, or raise NavigationError for a missing parent."""
        node = self._reader.node(key)
        rows = self._reader.children(key, limit + 1, offset)
        truncated = len(rows) > limit
        return self.response({"nodes": rows[:limit], "truncated": truncated, "nextOffset": offset + limit if truncated else None},
                             {"key": key, "limit": limit, "offset": offset}, [node, *rows[:limit]])

    def context(self, request: TraversalRequest) -> Record:
        """Return bounded breadth-first context, cutoff reasons, and snapshot metadata."""
        walk = traverse(self._reader, request)
        filters = {"key": request.key, "direction": request.direction, "relations": request.relations,
                   "depth": request.depth, "maxNodes": request.max_nodes, "maxEdges": request.max_edges}
        return self.response(walk.output(), filters, list(walk.nodes.values()))

    def path(self, request: PathRequest) -> Record:
        """Return a shortest discovered route with traversal bounds and diagnostics.

        Validate both endpoints through the reader. An unreached target is
        unknown if traversal stopped at a bound, otherwise not_found.
        """
        self._reader.node(request.target)
        options = request.traversal
        walk = traverse(self._reader, options)
        filters = {"from": options.key, "to": request.target, "direction": options.direction,
                   "relations": options.relations, "maxDepth": options.depth,
                   "maxNodes": options.max_nodes, "maxEdges": options.max_edges}
        return self.response({**walk.output(), **route(walk, options.key, request.target)}, filters, list(walk.nodes.values()))

    def sources(self, keys: list[str], max_lines: int, start_line: int | None) -> Record:
        """Return hash-verified local excerpts in key order with per-source statuses.

        Use a one-based start line within each node's span, defaulting to its
        first line. Missing keys raise NavigationError before reading files.
        """
        nodes = [self._reader.node(key) for key in keys]
        options = SourceOptions(max_lines, start_line)
        excerpts = [{"stableKey": node["stableKey"], **source_excerpt(self._reader, node, options)} for node in nodes]
        return self.response({"sources": excerpts}, {"keys": keys, "maxLines": max_lines, "startLine": start_line}, nodes)

    def source(self, key: str, max_lines: int, start_line: int | None) -> Record:
        """Return a verified excerpt/status; a missing key raises NavigationError.

        Bound lines to the node span and max_lines, starting at the one-based
        start_line or the span's first line. Never return unverified source.
        """
        node = self._reader.node(key)
        payload = source_excerpt(self._reader, node, SourceOptions(max_lines, start_line))
        return self.response({"source": payload}, {"key": key, "maxLines": max_lines, "startLine": start_line}, [node])
