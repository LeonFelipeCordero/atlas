"""Mapped ORM projections for navigation; transport records contain no ORM objects."""

from sqlalchemy import Select, select

from .models import GraphEdgeRow, GraphNodeMetricRow, GraphNodeRow, GraphSymbolRow


def nodes(repository_id: str) -> Select:
    node, symbol = GraphNodeRow, GraphSymbolRow
    return select(
        node.node_key.label("stableKey"), node.parent_key.label("parentStableKey"),
        node.type, node.kind, node.level, node.name, node.language,
        node.qualified_name.label("qualifiedName"), node.path,
        symbol.start_line.label("startLine"), symbol.start_column.label("startColumn"),
        symbol.end_line.label("endLine"), symbol.end_column.label("endColumn"),
        symbol.signature, symbol.visibility,
    ).outerjoin(symbol, (symbol.repository_id == node.repository_id) & (symbol.node_key == node.node_key)).where(node.repository_id == repository_id)


def metrics(repository_id: str, key: str) -> Select:
    metric = GraphNodeMetricRow
    return select(
        metric.line_count.label("lineCount"), metric.parameter_count.label("parameterCount"),
        metric.base_complexity.label("baseCyclomaticComplexity"),
        metric.nested_complexity.label("nestedCyclomaticComplexity"),
        metric.loop_complexity.label("loopNestedComplexity"),
        metric.total_complexity.label("cyclomaticComplexity"),
        metric.max_decision_depth.label("maxDecisionDepth"),
    ).where(metric.repository_id == repository_id, metric.node_key == key)


def adjacency(repository_id: str, key: str, outgoing: bool, relation: str, limit: int) -> Select:
    edge = GraphEdgeRow
    endpoint = edge.source_key if outgoing else edge.target_key
    index = "graph_edges_source" if outgoing else "graph_edges_target"
    # Each endpoint/relation equality uses the first three index columns. LIMIT
    # streams ordinal order without scanning/sorting unrelated or high-degree edges.
    return select(
        edge.ordinal, edge.source_key.label("sourceStableKey"), edge.target_key.label("targetStableKey"),
        edge.relationship.label("type"), edge.confidence, edge.path, edge.evidence,
        edge.line, edge.type_only.label("typeOnly"),
    ).with_hint(edge, index, dialect_name="sqlite").where(
        edge.repository_id == repository_id, endpoint == key, edge.relationship == relation,
    ).order_by(edge.ordinal).limit(limit)
