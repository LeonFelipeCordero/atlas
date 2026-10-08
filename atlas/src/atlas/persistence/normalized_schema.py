"""Version 2 relational graph schema (also used by the immutable v2 migration)."""

from sqlalchemy import (
    Column,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
)

metadata = MetaData()
# Referenced tables are reflected by the migration; this stub resolves graph FKs.
Table("repository_graphs", metadata, Column("repository_id", Text, primary_key=True))


def graph_table(name: str, *columns, constraints=()) -> Table:
    return Table(
        name,
        metadata,
        Column("repository_id", Text, primary_key=True),
        *columns,
        ForeignKeyConstraint(
            ["repository_id"], ["repository_graphs.repository_id"], ondelete="CASCADE"
        ),
        *constraints,
    )


def node_fk(column: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["repository_id", column],
        ["graph_nodes.repository_id", "graph_nodes.stable_key"],
        ondelete="CASCADE",
        deferrable=True,
        initially="DEFERRED",
    )


nodes = graph_table(
    "graph_nodes",
    Column("stable_key", Text, primary_key=True),
    Column("position", Integer, nullable=False),
    *[
        Column(name, Text, nullable=False)
        for name in ("type", "kind", "level", "name", "qualified_name")
    ],
    *[
        Column(name, Text)
        for name in ("language", "path", "parent_stable_key", "signature")
    ],
    *[
        Column(name, Integer)
        for name in ("start_line", "start_column", "end_line", "end_column")
    ],
    Column("depth", Integer, nullable=False),
    constraints=(node_fk("parent_stable_key"),),
)
Index(
    "graph_nodes_classification",
    nodes.c.repository_id,
    nodes.c.level,
    nodes.c.kind,
    nodes.c.language,
)
Index("graph_nodes_path", nodes.c.repository_id, nodes.c.path)
Index("graph_nodes_parent", nodes.c.repository_id, nodes.c.parent_stable_key)

edges = graph_table(
    "graph_edges",
    Column("position", Integer, primary_key=True),
    *[
        Column(name, Text, nullable=False)
        for name in (
            "source_stable_key",
            "target_stable_key",
            "type",
            "confidence",
            "path",
        )
    ],
    Column("line", Integer, nullable=False),
    Column("evidence", Text),
    constraints=(node_fk("source_stable_key"), node_fk("target_stable_key")),
)
Index(
    "graph_edges_source", edges.c.repository_id, edges.c.source_stable_key, edges.c.type
)
Index(
    "graph_edges_target", edges.c.repository_id, edges.c.target_stable_key, edges.c.type
)

ancestors = graph_table(
    "graph_node_ancestors",
    Column("node_stable_key", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("ancestor_stable_key", Text, nullable=False),
    constraints=(node_fk("node_stable_key"), node_fk("ancestor_stable_key")),
)
Index(
    "graph_ancestors_lookup", ancestors.c.repository_id, ancestors.c.ancestor_stable_key
)

properties = graph_table(
    "graph_node_properties",
    Column("node_stable_key", Text, primary_key=True),
    Column("name", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("value_type", Text, nullable=False),
    Column("text_value", Text),
    Column("number_value", Float),
    constraints=(node_fk("node_stable_key"),),
)
Index(
    "graph_properties_numeric",
    properties.c.repository_id,
    properties.c.name,
    properties.c.number_value,
)

languages = graph_table(
    "graph_languages",
    Column("position", Integer, primary_key=True),
    Column("language", Text, nullable=False),
)
stats = graph_table(
    "graph_stats",
    Column("name", Text, primary_key=True),
    Column("value", Integer, nullable=False),
)
repository_metadata = graph_table(
    "graph_metadata",
    Column("name", Text, primary_key=True),
    Column("value", Text, nullable=False),
)
diagnostics = graph_table(
    "graph_diagnostics",
    Column("position", Integer, primary_key=True),
    *[
        Column(name, Text, nullable=False)
        for name in ("severity", "path", "language", "message")
    ],
)
view_nodes = graph_table(
    "graph_view_nodes",
    Column("level", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("node_stable_key", Text, nullable=False),
    constraints=(node_fk("node_stable_key"),),
)
view_edges = graph_table(
    "graph_view_edges",
    Column("level", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("source_stable_key", Text, nullable=False),
    Column("target_stable_key", Text, nullable=False),
    Column("count", Integer, nullable=False),
    constraints=(node_fk("source_stable_key"), node_fk("target_stable_key")),
)
Index(
    "graph_view_edges_source",
    view_edges.c.repository_id,
    view_edges.c.level,
    view_edges.c.source_stable_key,
)
Index(
    "graph_view_edges_target",
    view_edges.c.repository_id,
    view_edges.c.level,
    view_edges.c.target_stable_key,
)
view_counts = graph_table(
    "graph_view_edge_counts",
    Column("level", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("category", Text, primary_key=True),
    Column("name", Text, primary_key=True),
    Column("count", Integer, nullable=False),
    constraints=(
        ForeignKeyConstraint(
            ["repository_id", "level", "position"],
            [
                "graph_view_edges.repository_id",
                "graph_view_edges.level",
                "graph_view_edges.position",
            ],
            ondelete="CASCADE",
        ),
    ),
)

cycle_groups = graph_table(
    "graph_cycle_groups",
    Column("group_id", Text, primary_key=True),
    Column("position", Integer, nullable=False),
)


def cycle_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["repository_id", "group_id"],
        ["graph_cycle_groups.repository_id", "graph_cycle_groups.group_id"],
        ondelete="CASCADE",
    )


cycle_nodes = graph_table(
    "graph_cycle_nodes",
    Column("group_id", Text, primary_key=True),
    Column("role", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("node_stable_key", Text, nullable=False),
    constraints=(cycle_fk(), node_fk("node_stable_key")),
)
Index(
    "graph_cycle_nodes_lookup",
    cycle_nodes.c.repository_id,
    cycle_nodes.c.node_stable_key,
)
cycle_edges = graph_table(
    "graph_cycle_edges",
    Column("group_id", Text, primary_key=True),
    Column("position", Integer, primary_key=True),
    *[
        Column(name, Text, nullable=False)
        for name in (
            "source_stable_key",
            "target_stable_key",
            "type",
            "confidence",
            "path",
        )
    ],
    Column("line", Integer, nullable=False),
    Column("evidence", Text),
    constraints=(
        cycle_fk(),
        node_fk("source_stable_key"),
        node_fk("target_stable_key"),
    ),
)

# Parents precede children for insertion; deletion uses the reverse order.
TABLES = [
    nodes,
    edges,
    ancestors,
    properties,
    languages,
    stats,
    repository_metadata,
    diagnostics,
    view_nodes,
    view_edges,
    view_counts,
    cycle_groups,
    cycle_nodes,
    cycle_edges,
]
