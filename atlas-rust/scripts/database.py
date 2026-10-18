"""Read-only SQLite inspection. Compare all schema objects and every stored row."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID


def connect(path: Path) -> closing[sqlite3.Connection]:
    return closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True))


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def backup(source: Path, target: Path) -> None:
    with connect(source) as original, closing(sqlite3.connect(target)) as destination:
        original.backup(destination)


def revision(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with connect(path) as database:
            row = database.execute("SELECT graph_revision FROM repository_graphs").fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def uuid_fixture(path: Path) -> str | None:
    value = revision(path)
    if value is not None:
        identity = UUID(value)
        if identity.version != 4 or identity.hex != value:
            raise ValueError(f"graph_revision must be uuid4().hex, got {value!r}")
    return value


def contents(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    with connect(path) as database:
        objects = database.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        tables = [row[1] for row in objects if row[0] == "table"]
        return {"exists": True, "journal_mode": database.execute("PRAGMA journal_mode").fetchone()[0],
                "integrity_check": database.execute("PRAGMA integrity_check").fetchall(),
                "foreign_key_check": database.execute("PRAGMA foreign_key_check").fetchall(),
                "schema": {table: schema(database, table) for table in tables},
                "objects": [list(row) for row in objects if row[0] in {"view", "trigger"}],
                "data": {table: rows(database, table) for table in tables}}


def schema(database: sqlite3.Connection, table: str) -> dict:
    indexes = database.execute(f"PRAGMA index_list({quote(table)})").fetchall()
    return {"columns": database.execute(f"PRAGMA table_xinfo({quote(table)})").fetchall(),
            "foreign_keys": database.execute(f"PRAGMA foreign_key_list({quote(table)})").fetchall(),
            "indexes": {index[1]: {"unique": index[2], "origin": index[3], "partial": index[4],
                                   "columns": database.execute(f"PRAGMA index_xinfo({quote(index[1])})").fetchall(),
                                   "sql": database.execute("SELECT sql FROM sqlite_master WHERE name=?", (index[1],)).fetchone()[0]}
                        for index in indexes},
            # Preserve constraints (including DEFERRABLE) not exposed through PRAGMAs.
            "sql": database.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]}


def rows(database: sqlite3.Connection, table: str) -> list[dict]:
    columns = [row[1] for row in database.execute(f"PRAGMA table_info({quote(table)})")]
    ordering = ", ".join(quote(column) for column in columns)
    records = database.execute(f"SELECT * FROM {quote(table)} ORDER BY {ordering}").fetchall()
    return [decode(dict(zip(columns, record))) for record in records]


def decode(record: dict) -> dict:
    # JSON serialization whitespace/key order is not graph data. Arrays stay ordered.
    if isinstance(record.get("payload"), str):
        try:
            record["payload"] = json.loads(record["payload"])
        except ValueError:
            pass
    return record


def keys(path: Path) -> tuple[str, str, str, str]:
    with connect(path) as database:
        file = database.execute("SELECT node_key FROM graph_nodes WHERE level='file' ORDER BY ordinal LIMIT 1").fetchone()
        callables = database.execute("SELECT node_key FROM graph_nodes WHERE level='callable' ORDER BY ordinal LIMIT 2").fetchall()
        root = database.execute("SELECT node_key FROM graph_nodes WHERE level='repository' ORDER BY ordinal LIMIT 1").fetchone()
        nodes = callables or ([file] if file else [root])
        if not nodes[0]:
            raise ValueError("No graph nodes available for navigation matrix")
        return ((root or file or nodes[0])[0], (file or nodes[0])[0], nodes[0][0], nodes[-1][0])


def languages(path: Path) -> list[dict]:
    with connect(path) as database:
        return [{"language": row[0], "files": row[1]} for row in database.execute(
            "SELECT language, count(*) FROM graph_nodes WHERE level='file' GROUP BY language ORDER BY language")]
