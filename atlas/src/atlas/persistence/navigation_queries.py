"""Mapped ORM projections for navigation; transport records contain no ORM objects."""

from dataclasses import dataclass

from sqlalchemy import Select, select

from .models import GraphEdgeRow, GraphNodeMetricRow, GraphNodeRow, GraphSymbolRow

METRIC_COLUMNS = (
    GraphNodeMetricRow.line_count.label("lineCount"),
    GraphNodeMetricRow.parameter_count.label("parameterCount"),
    GraphNodeMetricRow.base_complexity.label("baseCyclomaticComplexity"),
    GraphNodeMetricRow.nested_complexity.label("nestedCyclomaticComplexity"),
    GraphNodeMetricRow.loop_complexity.label("loopNestedComplexity"),
    GraphNodeMetricRow.total_complexity.label("cyclomaticComplexity"),
    GraphNodeMetricRow.max_decision_depth.label("maxDecisionDepth"),
)
EDGE_COLUMNS = (
    GraphEdgeRow.source_key.label("sourceStableKey"),
    GraphEdgeRow.target_key.label("targetStableKey"),
    GraphEdgeRow.relationship.label("type"), GraphEdgeRow.confidence,
    GraphEdgeRow.path, GraphEdgeRow.evidence, GraphEdgeRow.line,
    GraphEdgeRow.type_only.label("typeOnly"),
)


def nodes(repository_id: str) -> Select:
    """Build a repository-scoped node projection with optional symbol fields.

    Return an unexecuted select; callers add filtering, ordering, and limits.
    """
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
    """Build an unexecuted metric projection for a repository-local stable key."""
    metric = GraphNodeMetricRow
    return select(*METRIC_COLUMNS).where(metric.repository_id == repository_id, metric.node_key == key)


@dataclass(frozen=True)
class AdjacencyRequest:
    repository_id: str
    key: str
    outgoing: bool
    relation: str
    limit: int


def adjacency(request: AdjacencyRequest) -> Select:
    """Build an ordinal-ordered, limited edge select for one endpoint/relation.

    Use the source index for outgoing edges and the target index otherwise;
    the navigation SQLite compiler renders the index hint at execution.
    """
    edge = GraphEdgeRow
    endpoint = edge.source_key if request.outgoing else edge.target_key
    index = "graph_edges_source" if request.outgoing else "graph_edges_target"
    # Each endpoint/relation equality uses the first three index columns. LIMIT
    # streams ordinal order without scanning/sorting unrelated or high-degree edges.
    return select(edge.ordinal, *EDGE_COLUMNS).with_hint(edge, index, dialect_name="sqlite").where(
        edge.repository_id == request.repository_id, endpoint == request.key, edge.relationship == request.relation,
    ).order_by(edge.ordinal).limit(request.limit)
