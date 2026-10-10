"""Concrete read repository for focused normalized summaries and report facts."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.domain.repositories import (
    GraphDTO, GraphStatsDTO, ReportFactsDTO, ReportImportDTO, ReportNodeDTO,
)
from .models import (
    GraphDiagnosticRow, GraphEdgeRow, GraphNodeMetricRow, GraphNodeRow,
    GraphSymbolRow, RepositoryGraphRow,
)


class GraphReadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def graph(self, identifier: str) -> GraphDTO | None:
        self.session.rollback()
        with self.session.begin():
            row = self.session.get(RepositoryGraphRow, identifier)
            return self._graph_summary(row) if row and row.graph_revision else None

    def report_facts(self, identifier: str) -> ReportFactsDTO | None:
        self.session.rollback()
        with self.session.begin():
            row = self.session.get(RepositoryGraphRow, identifier)
            return self._report_facts(row) if row and row.graph_revision else None

    def _graph_summary(self, row: RepositoryGraphRow) -> GraphDTO:
        counts = self.session.execute(
            select(GraphNodeRow.level, func.count()).where(
                GraphNodeRow.repository_id == row.repository_id
            ).group_by(GraphNodeRow.level)
        ).all()
        levels = dict(counts)
        symbols = self._count(GraphSymbolRow, row.repository_id)
        edges = self._count(GraphEdgeRow, row.repository_id)
        diagnostics = self._count(GraphDiagnosticRow, row.repository_id)
        assert row.graph_revision is not None
        return GraphDTO(
            repositoryId=row.repository_id, graphRevision=row.graph_revision,
            schemaVersion=row.schema_version, indexedAt=row.indexed_at,
            rootName=row.root_name, rootPath=row.root_path, importedAt=row.imported_at,
            stats=GraphStatsDTO(
                files=levels.get("file", 0), symbols=symbols,
                modules=levels.get("module", 0), types=levels.get("type", 0),
                callables=levels.get("callable", 0), nodes=sum(levels.values()),
                edges=edges, externalNodes=levels.get("external", 0), parseErrors=diagnostics,
            ),
        )

    def _count(self, entity: type[GraphSymbolRow] | type[GraphEdgeRow] | type[GraphDiagnosticRow], identifier: str) -> int:
        return self.session.scalar(select(func.count()).select_from(entity).where(
            entity.repository_id == identifier
        )) or 0

    def _report_facts(self, row: RepositoryGraphRow) -> ReportFactsDTO:
        node, symbol, metric = GraphNodeRow, GraphSymbolRow, GraphNodeMetricRow
        records = self.session.execute(select(
            node.node_key.label("stableKey"), node.parent_key.label("parentStableKey"),
            node.type, node.level, node.kind, node.name,
            node.qualified_name.label("qualifiedName"), node.path,
            symbol.start_line.label("startLine"), metric.line_count.label("lineCount"),
            metric.parameter_count.label("parameterCount"),
            metric.base_complexity.label("baseCyclomaticComplexity"),
            metric.nested_complexity.label("nestedCyclomaticComplexity"),
            metric.total_complexity.label("cyclomaticComplexity"),
            metric.loop_complexity.label("loopNestedComplexity"),
            metric.max_decision_depth.label("maxDecisionDepth"),
        ).outerjoin(symbol, (symbol.repository_id == node.repository_id) & (symbol.node_key == node.node_key))
          .outerjoin(metric, (metric.repository_id == node.repository_id) & (metric.node_key == node.node_key))
          .where(node.repository_id == row.repository_id).order_by(node.ordinal)).mappings()
        nodes = [ReportNodeDTO.model_validate(record) for record in records]
        edge = GraphEdgeRow
        records = self.session.execute(select(
            edge.source_key.label("sourceStableKey"), edge.target_key.label("targetStableKey"),
            edge.relationship.label("type"), edge.confidence, edge.path, edge.line,
            edge.evidence, edge.type_only.label("typeOnly"),
        ).where(edge.repository_id == row.repository_id, edge.relationship != "CONTAINS")
          .order_by(edge.ordinal)).mappings()
        edges = [ReportImportDTO.model_validate(record) for record in records]
        diagnostic = GraphDiagnosticRow
        diagnostics = self.session.execute(select(
            diagnostic.severity, diagnostic.path, diagnostic.language, diagnostic.message,
        ).where(diagnostic.repository_id == row.repository_id)
          .order_by(diagnostic.ordinal)).mappings()
        assert row.graph_revision is not None
        return ReportFactsDTO(
            graphRevision=row.graph_revision, nodes=nodes, edges=edges,
            imports=[edge for edge in edges if edge.type == "IMPORTS"],
            diagnostics=[dict(record) for record in diagnostics],
        )
