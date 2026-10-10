"""SQLAlchemy models for registered repositories and their latest graphs."""

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("repositories_name_unique", func.lower(name), unique=True),)


class RepositoryGraphRow(Base):
    __tablename__ = "repository_graphs"

    repository_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    artifact: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class GraphNodeRow(Base):
    __tablename__ = "graph_nodes"

    repository_id: Mapped[str] = mapped_column(Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    parent_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualified_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "ordinal"),
        ForeignKeyConstraint(["repository_id", "parent_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        Index("graph_nodes_parent", "repository_id", "parent_key"),
        Index("graph_nodes_level", "repository_id", "level"),
        Index("graph_nodes_name", "repository_id", name.collate("NOCASE")),
        Index("graph_nodes_path", "repository_id", "path"),
    )


class GraphFileRow(Base):
    __tablename__ = "graph_files"

    repository_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    byte_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )


class GraphSymbolRow(Base):
    __tablename__ = "graph_symbols"

    repository_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )


class GraphNodeMetricRow(Base):
    __tablename__ = "graph_node_metrics"

    repository_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parameter_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nested_complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loop_complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_decision_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="CASCADE"),
    )


class GraphNodeDecoratorRow(Base):
    __tablename__ = "graph_node_decorators"

    repository_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    decorator: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "node_key"], ["graph_symbols.repository_id", "graph_symbols.node_key"], ondelete="CASCADE"),
    )


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"

    repository_id: Mapped[str] = mapped_column(Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    source_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_key: Mapped[str] = mapped_column(Text, nullable=False)
    relationship: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type_only: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "source_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION"),
        ForeignKeyConstraint(["repository_id", "target_key"], ["graph_nodes.repository_id", "graph_nodes.node_key"], ondelete="NO ACTION"),
        Index("graph_edges_source", "repository_id", "source_key", "relationship", "ordinal"),
        Index("graph_edges_target", "repository_id", "target_key", "relationship", "ordinal"),
    )


class GraphDiagnosticRow(Base):
    __tablename__ = "graph_diagnostics"

    repository_id: Mapped[str] = mapped_column(Text, ForeignKey("repository_graphs.repository_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("graph_diagnostics_path", "repository_id", "path"),)
