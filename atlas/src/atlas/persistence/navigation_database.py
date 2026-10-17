"""Repository-owned read-only driver setup, schema inspection and index hints."""

from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as SqliteConnection
from typing import Generator, cast

from sqlalchemy import Connection, URL, create_engine, event, inspect
from sqlalchemy.dialects.sqlite.base import SQLiteCompiler
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas.domain.navigation import NavigationError
from .database import default_database_path
from .models import GraphEdgeRow

REQUIRED_TABLES = {"repositories", "repository_graphs", "graph_nodes", "graph_files", "graph_symbols", "graph_node_metrics", "graph_node_decorators", "graph_edges", "graph_diagnostics"}
REQUIRED_INDEXES = {"graph_nodes_parent", "graph_nodes_name", "graph_nodes_path", "graph_edges_source", "graph_edges_target", "graph_diagnostics_path"}
EDGE_INDEXES = {"graph_edges_source", "graph_edges_target"}


class IndexedSQLiteCompiler(SQLiteCompiler):
    """Render SQLite's endpoint index hint on an ORM table, never a query string."""

    def get_from_hint_text(self, table, text: str | None) -> str:
        """Render an adjacency INDEXED BY hint; reject other tables/hints with ValueError."""
        if table is not GraphEdgeRow.__table__ or text not in EDGE_INDEXES:
            raise ValueError("Only the two graph adjacency indexes may be hinted")
        return f"INDEXED BY {text}"


def _check_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    indexed_tables = {"graph_nodes", "graph_edges", "graph_diagnostics"} & tables
    indexes = {index["name"] for table in indexed_tables for index in inspector.get_indexes(table)}
    missing = sorted((REQUIRED_TABLES - tables) | (REQUIRED_INDEXES - indexes))
    if missing:
        raise NavigationError(f"Missing graph schema/index: {', '.join(missing)}. Explicitly migrate and index the project.")


@contextmanager
def readonly_session(path: str | Path | None = None) -> Generator[Session, None, None]:
    """Yield a query-only session on an existing database after schema checks.

    Open the supplied/default path without creating directories or migrating.
    Keep one read transaction until exit, then close without committing.
    Raise NavigationError for missing schema/indexes or SQLAlchemy failures.
    """
    target = (Path(path).expanduser() if path is not None else default_database_path()).resolve()
    url = URL.create("sqlite+pysqlite", database=target.as_uri() + "?mode=ro", query={"uri": "true"})
    engine = create_engine(url)
    engine.dialect.statement_compiler = IndexedSQLiteCompiler

    @event.listens_for(engine, "connect")
    def configure(connection: object, _record: object) -> None:
        sqlite = cast(SqliteConnection, connection)
        sqlite.isolation_level = None
        sqlite.execute("PRAGMA query_only=ON").close()

    @event.listens_for(engine, "begin")
    def begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    try:
        with Session(engine) as session:
            _check_schema(session.connection())
            yield session
    except SQLAlchemyError as error:
        raise NavigationError(f"Cannot read graph database {target}: {error}. Index the project after explicitly migrating the database.") from error
    finally:
        engine.dispose()
