"""Maintain queryable relational graph data alongside the UI artifact snapshot."""

import re
from typing import Any

from sqlalchemy import delete

from . import normalized_schema as schema

EDGE_FIELDS = (
    "sourceStableKey",
    "targetStableKey",
    "type",
    "confidence",
    "path",
    "line",
    "evidence",
)
VALUE_TYPES = {
    type(None): "null",
    bool: "boolean",
    int: "number",
    float: "number",
    str: "text",
    list: "array",
    dict: "object",
}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _escape(name: str) -> str:
    return name.replace("~", "~0").replace("/", "~1")


def _object_values(name: str, value: dict[str, Any], position: int):
    for key, item in value.items():
        yield from _property_values(f"{name}/{_escape(key)}", item, position)


def _array_values(name: str, value: list[Any]):
    for index, item in enumerate(value):
        path = f"{name}/{index}" if isinstance(item, (dict, list)) else name
        yield from _property_values(path, item, index)


def _property_values(name: str, value: Any, position: int = 0):
    """Flatten extension objects into escaped slash paths and arrays into rows."""
    if isinstance(value, dict) and value:
        yield from _object_values(name, value, position)
        return
    if isinstance(value, list) and value:
        yield from _array_values(name, value)
        return
    yield dict(
        name=name,
        position=position,
        value_type=VALUE_TYPES[type(value)],
        number_value=float(value) if isinstance(value, (int, float)) else None,
        text_value=value if isinstance(value, str) else None,
    )


def _node_fields(node: dict[str, Any]):
    return {
        _snake(key): value
        for key, value in node.items()
        if key not in ("properties", "ancestorStableKeys")
    }


def _edge_fields(edge: dict[str, Any]):
    return {_snake(key): edge[key] for key in EDGE_FIELDS}


def _add_ancestors(node: dict[str, Any], add) -> None:
    for index, ancestor in enumerate(node.get("ancestorStableKeys", [])):
        add(
            schema.ancestors,
            node_stable_key=node["stableKey"],
            position=index,
            ancestor_stable_key=ancestor,
        )


def _add_property(key: str, name: str, value: Any, add) -> None:
    for property_value in _property_values(_escape(name), value):
        add(schema.properties, node_stable_key=key, **property_value)


def _add_properties(node: dict[str, Any], add) -> None:
    for name, value in node.get("properties", {}).items():
        _add_property(node["stableKey"], name, value, add)


def _add_entities(artifact: dict[str, Any], add) -> None:
    for position, node in enumerate(artifact.get("nodes", [])):
        add(schema.nodes, position=position, **_node_fields(node))
        _add_ancestors(node, add)
        _add_properties(node, add)
    for position, edge in enumerate(artifact.get("edges", [])):
        # Endpoint classifications are available by joining graph_nodes.
        add(schema.edges, position=position, **_edge_fields(edge))


def _add_count_category(level: str, position: int, category: str, counts, add) -> None:
    for name, count in counts.items():
        add(
            schema.view_counts,
            level=level,
            position=position,
            category=category,
            name=name,
            count=count,
        )


def _add_counts(level: str, position: int, edge: dict[str, Any], add) -> None:
    for category in ("relationship", "confidence"):
        _add_count_category(level, position, category, edge[f"{category}Counts"], add)


def _add_view_nodes(level: str, nodes: list[str], add) -> None:
    for position, key in enumerate(nodes):
        add(schema.view_nodes, level=level, position=position, node_stable_key=key)


def _add_view_edges(level: str, edges: list[dict[str, Any]], add) -> None:
    for position, edge in enumerate(edges):
        add(
            schema.view_edges,
            level=level,
            position=position,
            source_stable_key=edge["sourceStableKey"],
            target_stable_key=edge["targetStableKey"],
            count=edge["count"],
        )
        _add_counts(level, position, edge, add)


def _add_views(artifact: dict[str, Any], add) -> None:
    for level, view in artifact.get("views", {}).items():
        _add_view_nodes(level, view["nodes"], add)
        _add_view_edges(level, view["edges"], add)


def _add_cycle_nodes(group_id: str, role: str, keys: list[str], add) -> None:
    for index, key in enumerate(keys):
        add(
            schema.cycle_nodes,
            group_id=group_id,
            role=role,
            position=index,
            node_stable_key=key,
        )


def _add_cycle_edges(group_id: str, edges: list[dict[str, Any]], add) -> None:
    for index, edge in enumerate(edges):
        add(schema.cycle_edges, group_id=group_id, position=index, **_edge_fields(edge))


def _add_cycle_groups(groups: list[dict[str, Any]], add) -> None:
    for position, group in enumerate(groups):
        add(schema.cycle_groups, group_id=group["id"], position=position)
        _add_cycle_nodes(group["id"], "member", group["nodeStableKeys"], add)
        _add_cycle_nodes(group["id"], "example", group["exampleCycle"], add)
        _add_cycle_edges(group["id"], group["edges"], add)


def _add_cycles(artifact: dict[str, Any], add) -> None:
    cycles = artifact.get("circularDependencies")
    if cycles is None:
        return
    add(
        schema.repository_metadata,
        name="circularDependenciesVersion",
        value=str(cycles["version"]),
    )
    _add_cycle_groups(cycles["groups"], add)


def _add_repository_metadata(artifact: dict[str, Any], add) -> None:
    repository = artifact.get("repository", {})
    for position, language in enumerate(repository.get("languages", [])):
        add(schema.languages, position=position, language=language)
    for name in ("path", "name", "indexedAt"):
        if name in repository:
            add(schema.repository_metadata, name=name, value=repository[name])
    add(
        schema.repository_metadata,
        name="schemaVersion",
        value=str(artifact.get("schemaVersion", 2)),
    )


def _add_analysis_metadata(artifact: dict[str, Any], add) -> None:
    for name, value in artifact.get("stats", {}).items():
        add(schema.stats, name=name, value=value)
    for position, diagnostic in enumerate(artifact.get("diagnostics", [])):
        add(schema.diagnostics, position=position, **diagnostic)


def _insert_rows(connection, table, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    # Explicit NULLs keep heterogeneous optional node fields in bulk inserts.
    connection.execute(table.insert(), [_complete_row(table, row) for row in rows])


def _complete_row(table, row: dict[str, Any]):
    return {column.name: row.get(column.name) for column in table.columns}


def replace_graph(connection, identifier: str, artifact: dict[str, Any]) -> None:
    """Replace one repository's rows inside the caller's transaction."""
    rows: dict[str, list[dict[str, Any]]] = {table.name: [] for table in schema.TABLES}

    def add(table, **values):
        rows[table.name].append({"repository_id": identifier, **values})

    _add_entities(artifact, add)
    _add_views(artifact, add)
    _add_cycles(artifact, add)
    _add_repository_metadata(artifact, add)
    _add_analysis_metadata(artifact, add)
    for table in reversed(schema.TABLES):
        connection.execute(delete(table).where(table.c.repository_id == identifier))
    for table in schema.TABLES:
        _insert_rows(connection, table, rows[table.name])
