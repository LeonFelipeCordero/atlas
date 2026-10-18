"""CLI migration validation, SQL hint boundaries and traversal fetch budgets."""

from unittest.mock import Mock

import pytest
from sqlalchemy.dialects.sqlite import dialect

from atlas.domain.navigation import TraversalRequest
from atlas.persistence import database
from atlas.persistence.models import GraphEdgeRow, GraphNodeRow
from atlas.persistence.navigation_database import IndexedSQLiteCompiler
from atlas.services.navigation_walk import Traversal


@pytest.mark.parametrize("arguments", [[], ["wrong"], ["wrong", "path"], ["migrate", "path", "extra"]])
def test_migration_cli_rejects_invalid_arguments(monkeypatch, arguments):
    migrate = Mock()
    monkeypatch.setattr(database.sys, "argv", ["database", *arguments])
    monkeypatch.setattr(database, "migrate_database", migrate)
    with pytest.raises(SystemExit, match="Usage:"):
        database.main()
    migrate.assert_not_called()


@pytest.mark.parametrize("arguments,expected", [(["migrate"], None), (["migrate", "custom.sqlite"], "custom.sqlite")])
def test_migration_cli_optional_path(monkeypatch, arguments, expected):
    migrate = Mock()
    monkeypatch.setattr(database.sys, "argv", ["database", *arguments])
    monkeypatch.setattr(database, "migrate_database", migrate)
    database.main()
    migrate.assert_called_once_with(expected)


@pytest.mark.parametrize("table,hint", [(GraphNodeRow.__table__, "graph_edges_source"), (GraphEdgeRow.__table__, "unsafe")])
def test_sql_hint_validates_table_and_index_independently(table, hint):
    with pytest.raises(ValueError, match="Only the two"):
        IndexedSQLiteCompiler(dialect(), None).get_from_hint_text(table, hint)


def test_traversal_fetch_budget_subtracts_already_visited_edges():
    reader = Mock()
    reader.node.return_value = {"stableKey": "a", "external": False}
    reader.edges.return_value = []
    request = TraversalRequest(key="a", direction="outgoing", relations=[], depth=3, max_nodes=10, max_edges=5)
    traversal = Traversal(reader, request)
    traversal.walk.edges[0] = {"ordinal": 0}
    traversal.walk.edges[1] = {"ordinal": 1}
    traversal.expand("a", 1)
    assert reader.edges.call_args.args[0].limit == 4
