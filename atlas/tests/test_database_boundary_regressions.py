"""Negative regressions for expression, dependency and infrastructure bypasses."""

import pytest

from tests.database_boundary_policy import INFRASTRUCTURE, REVISIONS
from tests.test_database_boundaries import violations


@pytest.mark.parametrize("source", [
    "from sqlalchemy import select, column\nsession.execute(select(column('(SELECT name FROM repositories LIMIT 1)', is_literal=True)))",
    "from sqlalchemy import column as c\nraw = c\nraw(fragment, is_literal=flag)",
    "from sqlalchemy.sql.elements import ColumnClause as C\nC(fragment, None, True)",
    "from sqlalchemy.sql.elements import TextClause as T\nsession.execute(T(fragment))",
    "from sqlalchemy.sql.expression import table as t, column as c\nselect(t(fragment, c(fragment, is_literal=True)))",
    "Row.id.op(fragment)(value)",
    "Row.__table__.c.name.is_literal = True",
    "from sqlalchemy.sql import quoted_name as name\nRow.__table__.c.name.name = name(fragment, False)",
    "operation = Row.id.bool_op\noperation(fragment)(value)",
    "select(Row).prefix_with(fragment)",
    "select(Row).suffix_with(fragment)",
    "from sqlalchemy.ext.compiler import compiles as render\n@render(Statement)\ndef query(element, compiler, **kw):\n    return fragment",
])
def test_raw_expression_alternatives_are_not_mapped_queries(source: str) -> None:
    assert violations("atlas.persistence.repositories", source)


@pytest.mark.parametrize("body", [
    "self.public = repository",
    "alias = repository\nself.public = alias",
    "alias = {'port': repository}\nself.public = alias",
    "return repository",
    "alias = repository\nreturn alias",
    "foreign_helper(repository)",
    "alias = repository\nforeign_helper(alias)",
    "self.other = repository\nreturn self.other",
])
@pytest.mark.parametrize("annotation", ["Port", "'Port'"])
@pytest.mark.parametrize("protocol, slot", [
    ("atlas.domain.repositories.RepositoryProtocol", "_repository"),
    ("atlas.domain.navigation.NavigationReader", "_reader"),
])
def test_annotated_constructor_parameters_cannot_escape(body: str, annotation: str, protocol: str, slot: str) -> None:
    module, name = protocol.rsplit(".", 1)
    source = f"""from {module} import {name} as Port
class Service:
    def __init__(self, r: {annotation}):
        self.{slot} = r
""" + "\n".join("        " + line.replace("repository", "r") for line in body.splitlines())
    assert violations("atlas.services.repositories", source)


@pytest.mark.parametrize("annotation", ["Port", "'Port'"])
def test_private_constructor_alias_and_domain_results_are_allowed(annotation: str) -> None:
    source = f"""from atlas.domain.repositories import RepositoryProtocol as Port
class Service:
    def __init__(self, r: {annotation}):
        alias = r
        self._repository = alias
    def data(self):
        return self._repository.list()
"""
    assert not violations("atlas.services.repositories", source)


@pytest.mark.parametrize("source", [
    "import operator\noperator.attrgetter('_repository')(service).list()",
    "from operator import attrgetter as lookup\nlookup('_reader')(service).overview()",
    "import operator as op\nlookup = op.attrgetter\nextract = lookup\nextract('_repository.list')(service)()",
    "from operator import attrgetter\nattrgetter(computed)(service)",
    "from operator import methodcaller as invoke\ninvoke('__getattribute__', '_repository')(service)",
])
def test_reflective_port_extraction_cannot_hide_in_operator_aliases(source: str) -> None:
    assert violations("atlas.cli.commands", source)


def test_public_domain_introspection_is_not_private_handle_extraction() -> None:
    assert not violations("atlas.metrics.introspection", "from operator import attrgetter as field\nfield('name', 'location')(dto)")


@pytest.mark.parametrize("source", [
    "from atlas.domain.repositories import RepositoryProtocol as Port\ndef outside(r: Port):\n    return r.list()",
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from atlas.domain.navigation import NavigationReader as Reader",
    "import atlas.domain.repositories as domain\nPort = domain.RepositoryProtocol",
])
def test_nonservice_helpers_cannot_accept_or_forward_ports(source: str) -> None:
    assert violations("atlas.helpers", source)


@pytest.mark.parametrize("module", sorted(INFRASTRUCTURE))
@pytest.mark.parametrize("source", [
    "from sqlalchemy.orm import Session\nsession.query(RepositoryRow).all()",
    "from sqlalchemy.orm import Session as S\ns = S(engine)\ns.query(Row).all()",
    "from sqlalchemy import select as mapped\nstatement = mapped(Row)",
    "from sqlalchemy.sql import Select as Query\nquery = Query(Row)",
    "session.get(RepositoryRow, id)",
    "session.add(row)",
    "session.bulk_save_objects(rows)",
    "session.bulk_insert_mappings(Row, records)",
    "session.bulk_update_mappings(Row, records)",
    "Row.__table__.select()",
    "Row.__table__.update()",
    "read = session.query\nread(Row).all()",
])
def test_infrastructure_is_never_a_domain_orm_repository(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("module", sorted(REVISIONS))
@pytest.mark.parametrize("source", [
    "from alembic import op\nop.execute('DELETE FROM repositories')",
    "from alembic import op as migration\nwrite = migration.execute\nwrite(statement)",
    "from alembic import op\nop.bulk_insert(table, records)",
    "from alembic import op\nop.get_bind()",
    "from alembic import op\nop.execute('CREATE TABLE unsafe (id int)')",
    "connection.exec_driver_sql('PRAGMA query_only=ON')",
    "from sqlalchemy import text as raw\nraw('name COLLATE NOCASE')",
])
def test_revision_filename_is_not_a_data_or_text_query_exemption(module: str, source: str) -> None:
    assert violations(module, source)


def test_schema_ddl_and_existing_index_collation_remain_allowed() -> None:
    source = "from alembic import op as schema\nfrom sqlalchemy import Column, Text\nschema.create_table('example', Column('name', Text))"
    assert not violations(next(iter(REVISIONS)), source)
    source = "from alembic import op\nfrom sqlalchemy import text as expression\nop.create_index('graph_nodes_name', 'graph_nodes', ['repository_id', expression('name COLLATE NOCASE')])"
    module = "atlas.persistence.migrations.versions.0002_graph_nodes"
    assert not violations(module, source)
    assert violations(module, source.replace("name COLLATE NOCASE", "(SELECT name FROM repositories)"))
    assert violations(module, source + "\nexpression('name COLLATE NOCASE')")
