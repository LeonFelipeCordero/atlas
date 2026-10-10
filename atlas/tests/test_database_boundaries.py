"""Guard CLI -> service factories -> private domain ports <- exact ORM owners."""

import ast

import pytest

from tests.database_boundary_policy import (
    FACTORY_IMPORTS,
    INFRASTRUCTURE,
    ORM_MODULES,
    REPOSITORY_MODULES,
    REVISIONS,
    belongs_to as belongs_to,
    boundary_sensitive,
    boundary_violations,
    dynamic_import_violations as dynamic_import_violations,
    forbidden_imports,
    forbidden_prefixes as forbidden_prefixes,
    import_aliases as import_aliases,
    import_targets as import_targets,
    matches_forbidden_prefix as matches_forbidden_prefix,
    node_dynamic_violations as node_dynamic_violations,
    node_import_aliases as node_import_aliases,
    node_import_targets as node_import_targets,
    qualified_name as qualified_name,
    resolved_import_module as resolved_import_module,
)
from tests.test_architecture import ROOT, module_name, module_package


def violations(module: str, source: str) -> set[str]:
    return boundary_violations(module, source, module.rsplit(".", 1)[0])


@pytest.mark.parametrize("source, expected", [
    ("import sqlalchemy as sa", {"sqlalchemy"}),
    ("from sqlalchemy.orm import Session as S", {"sqlalchemy.orm", "sqlalchemy.orm.Session"}),
    ("from ..persistence import database as db", {"atlas.persistence", "atlas.persistence.database"}),
    ("from .. import persistence as db", {"atlas", "atlas.persistence"}),
    ("from atlas import persistence", {"atlas", "atlas.persistence"}),
    ("def run():\n    import sqlite3", {"sqlite3"}),
    ("if TYPE_CHECKING:\n    from ..persistence.models import RepositoryRow", {
        "atlas.persistence.models", "atlas.persistence.models.RepositoryRow",
    }),
    ("from ..bootstrap import repository_service", {"atlas.bootstrap", "atlas.bootstrap.repository_service"}),
])
def test_import_scan_resolves_database_boundary_syntax(source: str, expected: set[str]) -> None:
    assert import_targets(source, "atlas.cli") == expected


@pytest.mark.parametrize("module, target, blocked", [
    ("atlas.cli.commands", "sqlalchemy.orm", True),
    ("atlas.cli.commands", "sqlite3", True),
    ("atlas.cli.commands", "alembic.command", True),
    ("atlas.cli.commands", "atlas.persistence.database", True),
    ("atlas.cli.commands", "atlas.persistence", True),
    ("atlas.cli.commands", "atlas.bootstrap", False),
    ("atlas.cli.commands", "atlas.services.repositories", False),
    ("atlas.services.repositories", "atlas.persistence.repositories", True),
    ("atlas.services.repositories", "atlas.bootstrap", True),
    ("atlas.services.repositories", "atlas.cli.commands", True),
    ("atlas.services.repositories", "atlas.domain.repositories", False),
    ("atlas.domain.repositories", "atlas.persistence.models", True),
    ("atlas.domain.repositories", "atlas.services.repositories", True),
    ("atlas.indexer", "atlas.persistence.database", True),
    ("atlas.indexer", "atlas.bootstrap", True),
    ("atlas.bootstrap", "atlas.persistence.database", True),
    ("atlas.bootstrap", "sqlalchemy.orm", True),
    ("atlas.bootstrap", "atlas.services.factories", False),
    ("atlas.persistence.database", "atlas.bootstrap", True),
    ("atlas.persistence.database", "sqlalchemy.orm", False),
    ("atlas.persistence.migrations.env", "alembic", False),
    ("atlas.persistence.migrations.env", "atlas.persistence.models", False),
    ("atlas.persistence.repositories", "sqlalchemy.orm.Session", False),
    ("atlas.persistence.models", "atlas.domain.repositories", False),
    ("atlas.persistence.repositories", "atlas.services.repositories", True),
    ("atlas.persistence.models", "atlas.cli.commands", True),
    ("atlas.persistence.database", "atlas.domain.repositories", False),
    ("atlas.cli.commands", "sqlalchemy_helpers", False),
    ("atlas.persistence.other", "sqlalchemy", True),
    ("atlas.persistence.database.extra", "sqlite3", True),
    ("atlas.persistence.graph_records", "sqlalchemy", True),
    ("atlas.metrics.unrelated", "sqlite3", True),
    ("atlas.services.factories", "sqlalchemy.orm.Session", True),
    ("atlas.services.factories", "atlas.persistence.database.repository_session", True),
    ("atlas.services.factories", "atlas.persistence.repositories.RepositoryStore", True),
    ("atlas.services.factories", "atlas.persistence.navigation.GraphReader", True),
    ("atlas.services.factories", "atlas.persistence.repositories.repository_store", False),
    ("atlas.services.factories", "atlas.persistence.navigation.navigation_reader", False),
    ("atlas.services.factories", "atlas.persistence.database.migrate_database", False),
    ("atlas.persistence.migrations.versions.9999_other", "alembic.op", True),
])
def test_database_boundary_policy(module: str, target: str, blocked: bool) -> None:
    assert bool(forbidden_imports(module, {target})) is blocked


@pytest.mark.parametrize("module", [
    "atlas.services.repositories", "atlas.cli.commands", "atlas.metrics.adapters.python",
    "atlas.parsing.adapters", "atlas.unrelated.worker", "atlas.persistence.other",
])
@pytest.mark.parametrize("source", [
    "import atlas as app\napp.persistence.repositories.RepositoryStore",
    "def run():\n    from atlas.persistence import repositories as stores",
    "from typing import TYPE_CHECKING as TC\nif TC:\n    import atlas.persistence.models as entities",
    "import atlas.persistence as storage",
    "import sqlalchemy as sa\nfactory = sa.orm.Session\nfactory()",
    "from sqlalchemy.orm import Session as S\nAlias = S\nAlias()",
    "import atlas as app\nowner = app\nstores = owner.persistence.repositories\nstores.RepositoryStore(None)",
    "from atlas import persistence as storage\nStore = storage.repositories.RepositoryStore",
])
def test_aliases_local_and_type_imports_cannot_hide_storage(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("module", ["atlas.services.repositories", "atlas.parsing.adapters", "atlas.unrelated.worker"])
@pytest.mark.parametrize("source", [
    "import importlib as loader\nloader.import_module('atlas.persistence')",
    "from importlib import import_module as load",
    "def run():\n    __import__('atlas.persistence')",
    "import builtins as b\nload = b.__import__",
    "from builtins import __import__ as load",
    "if TYPE_CHECKING:\n    import runpy",
    "exec('import atlas.persistence')",
    "from atlas import *",
    "import builtins as b\nload = getattr(b, '__import__')\nload('sqlite3')",
    "import sys\nsys.modules['sqlalchemy'].orm.Session()",
    "getattr(service, '_repo' + 'sitory')",
    "vars(service)['_repository']",
    "object.__getattribute__(service, '_repository')",
    "getattr(orm, expression)",
    "load = getattr\nreflect = load\nreflect(service, computed_name)",
    "import builtins as b\nreflect = b.getattr\nreflect(service, computed_name)",
    "service.__dict__['_reader']",
    "globals()[computed_name]",
    "locals()[computed_name]",
    "setattr(service, computed_name, repository)",
    "delattr(service, computed_name)",
])
def test_dynamic_loading_is_detected_in_all_production(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("source", [
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from atlas.domain.repositories import RepositoryProtocol",
    "from sqlalchemy.orm import Session\nfrom atlas.persistence.models import RepositoryRow",
    "from alembic import op\nop.execute('SELECT importlib FROM legacy')",
])
def test_regular_imports_and_sql_strings_are_not_dynamic_loading(source: str) -> None:
    assert not dynamic_import_violations(source, "atlas.persistence")


def test_every_production_package_is_boundary_sensitive() -> None:
    assert all(boundary_sensitive(module) for module in (
        "atlas.parsing.adapters", "atlas.metrics.adapters.python", "atlas.persistence.repositories", "atlas.future.worker",
    ))


@pytest.mark.parametrize("source", [
    "from atlas.persistence.repositories import RepositoryStore\nservice = RepositoryStore(None)",
    "from atlas.services.repositories import RepositoryService",
    "from atlas.services.factories import repository_service\ndef repository_service():\n    return object()",
    "from atlas.services.factories import repository_service\nrepository_service()",
    "from atlas.services import factories\nrepository_service = factories.repository_service",
    "from atlas.services.factories import repository_service as another_service",
    "from atlas.services.factories import repository_service\n__all__ = ['RepositoryStore']",
])
def test_bootstrap_cannot_compose_or_gain_other_behavior(source: str) -> None:
    assert violations("atlas.bootstrap", source)


def test_bootstrap_only_reexports_service_factories() -> None:
    source = '''"""Compatibility factory exports."""
from atlas.services.factories import repository_service, navigation_service, migrate_database
__all__ = ["repository_service", "navigation_service", "migrate_database"]
'''
    assert not violations("atlas.bootstrap", source)


@pytest.mark.parametrize("target", sorted(FACTORY_IMPORTS))
def test_service_factory_exact_operation_imports_are_allowed(target: str) -> None:
    module, name = target.rsplit(".", 1)
    assert not violations("atlas.services.factories", f"from {module} import {name} as _operation")


@pytest.mark.parametrize("source", [
    "from atlas import persistence",
    "import atlas.persistence.repositories as stores",
    "from ..persistence.repositories import RepositoryStore",
    "from ..persistence.database import repository_session",
    "from ..persistence.navigation import GraphReader",
    "from ..persistence.repositories import repository_store\nsession.commit()",
    "from sqlalchemy.orm import Session",
    "def build():\n    return service._repository",
    "def build():\n    return service.session",
])
def test_factory_cannot_access_repository_implementation_or_handles(source: str) -> None:
    assert boundary_violations("atlas.services.factories", source, "atlas.services")


@pytest.mark.parametrize("module", ["atlas.services.repositories", "atlas.cli.commands", "atlas.unrelated.worker", "atlas.persistence.other"])
@pytest.mark.parametrize("source", [
    "session.execute(statement)", "connection.exec_driver_sql(sql)", "session.commit()",
    "session.scalars(statement)", "session.query(Row)", "cursor.executemany(sql, values)",
    "session.get(Row, key)", "session.add(row)", "session.add_all(rows)",
    "get_row = session.get\nget_row(Row, key)", "session.refresh(row)",
    "Session()", "sessionmaker()", "create_engine(url)", "select(Row)",
    "run = session.execute\nrun(statement)", "run = getattr(session, 'execute')\nrun(statement)",
    "connection = service.connection", "session = service._session", "engine = service.engine",
    "self.repository = repository", "self.reader = reader", "return_value = service._repository",
    "return_value = service._reader", "service.repository.list()",
])
def test_database_behavior_and_handle_access_without_imports_is_forbidden(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("source", [
    "from sqlalchemy import text as sql\nsession.execute(sql('SELECT * FROM repositories'))",
    "import sqlalchemy as sa\nraw = sa.text\nraw(statement)",
    "import sqlalchemy as sa\ngetattr(sa, 'text')(statement)",
    "session.execute('SELECT id FROM repositories')",
    "statement = 'SELECT id FROM repositories'\nsession.execute(statement)",
    "statement = f'SELECT id FROM {table}'\nsession.execute(statement)",
    "session.execute('DELETE FROM repositories')",
    "connection.exec_driver_sql(statement)",
    "connection.cursor()",
    "from sqlalchemy import literal_column\nliteral_column(expression)",
    "select(Row).from_statement(statement)",
])
@pytest.mark.parametrize("module", sorted(ORM_MODULES | {"atlas.services.repositories", "atlas.unrelated.worker"}))
def test_orm_owners_cannot_reintroduce_arbitrary_sql_or_driver_reads(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("module", sorted(INFRASTRUCTURE - REVISIONS))
def test_setup_sql_is_confined_to_exact_connection_infrastructure(module: str) -> None:
    assert not violations(module, "connection.exec_driver_sql('PRAGMA query_only=ON')")


@pytest.mark.parametrize("module", sorted(INFRASTRUCTURE - REVISIONS))
@pytest.mark.parametrize("source", [
    "connection.exec_driver_sql('SELECT id FROM repositories')",
    "connection.execute('UPDATE repositories SET name = 1')",
    "connection.execute('DELETE FROM repositories')",
    "connection.execute('INSERT INTO repositories VALUES (1)')",
    "from sqlalchemy import text as sql\nconnection.execute(sql('SELECT 1'))",
    "from sqlalchemy import text\nstatement = text(query)",
    "connection.exec_driver_sql(statement)",
    "connection.execute('PRAGMA query_only=OFF')",
    "connection.exec_driver_sql('BEGIN' if ready else 'SELECT 1')",
    "connection.execute('PRAGMA query_only=' + option)",
    "run = connection.execute\nrun(statement)",
    "sql = 'SELECT * FROM repositories'",
])
def test_infrastructure_cannot_become_raw_sql_repository(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("sql", [
    "PRAGMA busy_timeout = 30000", "PRAGMA foreign_keys = ON", "PRAGMA journal_mode = WAL",
    "PRAGMA query_only=ON", "BEGIN", "BEGIN IMMEDIATE",
])
def test_exact_literal_driver_setup_and_conditional_transaction_are_allowed(sql: str) -> None:
    assert not violations("atlas.persistence.database", f"cursor.execute({sql!r})")
    assert not violations("atlas.persistence.database", "connection.exec_driver_sql('BEGIN IMMEDIATE' if migrating else 'BEGIN')")


@pytest.mark.parametrize("module", [
    "atlas.persistence.other", "atlas.persistence.navigation.extra", "atlas.persistence.database_extra",
    "atlas.persistence.migrations.versions.0005_future", "atlas.persistence.migrations.env.extra",
])
def test_new_repository_or_migration_module_does_not_automatically_gain_db_ownership(module: str) -> None:
    assert violations(module, "import sqlite3\nconnection = sqlite3.connect('db')")


@pytest.mark.parametrize("source", [
    "from sqlalchemy import select\nfrom sqlalchemy.orm import Session\nsession.execute(select(Row))",
    "from sqlalchemy import insert, delete\nsession.execute(insert(Row), records)\nsession.execute(delete(Row))",
])
def test_exact_orm_repository_modules_can_use_mapped_queries(source: str) -> None:
    assert not violations("atlas.persistence.repositories", source)


@pytest.mark.parametrize("body", [
    "return self._repository", "return self._reader", "return {'repo': self._repository}",
    "dependency = self._repository\nreturn dependency", "yield self._reader",
    "return self._repository.register", "return self._reader.snapshot",
    "dependency = {'repo': self._repository}\nreturn dependency",
    "return foreign_helper(self._repository)", "foreign_helper(self._reader)",
    "self.public = self._repository", "return getattr(self, '_repository')",
])
def test_service_cannot_return_or_reexport_private_dependencies(body: str) -> None:
    source = "class Service:\n    def expose(self):\n" + "\n".join("        " + line for line in body.splitlines())
    assert violations("atlas.services.repositories", source)


@pytest.mark.parametrize("annotation", ["Any", "RepositoryStore", "Session", "object"])
def test_service_constructor_must_use_domain_protocol(annotation: str) -> None:
    source = f"class Service:\n    def __init__(self, repository: {annotation}):\n        self._repository = repository"
    assert violations("atlas.services.repositories", source)


@pytest.mark.parametrize("protocol, port, argument, method", [
    ("atlas.domain.repositories.RepositoryProtocol", "_repository", "repository", "list"),
    ("atlas.domain.navigation.NavigationReader", "_reader", "reader", "overview"),
])
def test_service_private_domain_protocol_composition_is_allowed(protocol: str, port: str, argument: str, method: str) -> None:
    module, name = protocol.rsplit(".", 1)
    source = f"""from {module} import {name} as Port
class Service:
    def __init__(self, {argument}: Port):
        self.{port} = {argument}
    def data(self):
        return self.{port}.{method}()
"""
    assert not violations("atlas.services.repositories", source)


def test_domain_graph_repository_is_not_a_database_repository() -> None:
    source = """from atlas.domain.models import ParsedRepository as Graph
class Index:
    def __init__(self, repository: Graph):
        self.repository = repository
    def files(self):
        return self.repository.files
"""
    assert not violations("atlas.metrics.adapters.resolution", source)
    assert violations("atlas.metrics.adapters.resolution", source + "\n    def bypass(self):\n        return self.repository.execute(statement)")


@pytest.mark.parametrize("source", [
    "from atlas.services.factories import _repository_store as load\nwith load() as repo:\n    pass",
    "import atlas.services.factories as f\nf._navigation_reader('project')",
    "from atlas.services.factories import repository_store",
    "from atlas.services import factories as f\nload = f._repository_store",
    "import atlas as app\nload = app.services.factories._migrate_database",
])
@pytest.mark.parametrize("module", ["atlas.cli.commands", "atlas.services.other", "atlas.unrelated.worker"])
def test_factory_public_api_cannot_launder_repository_access(module: str, source: str) -> None:
    assert violations(module, source)


@pytest.mark.parametrize("source", [
    "from atlas.persistence.repositories import repository_store as _store\ndef factory():\n    with _store() as repository:\n        yield repository",
    "from atlas.persistence.navigation import navigation_reader as _reader\ndef factory():\n    with _reader('p') as reader:\n        dependency = {'reader': reader}\n        return dependency",
    "from atlas.persistence.repositories import repository_store",
])
def test_factory_context_cannot_expose_ports(source: str) -> None:
    assert violations("atlas.services.factories", source)


def test_service_reader_helpers_are_service_owned() -> None:
    source = "from atlas.services.navigation_walk import traverse\nfrom atlas.services.navigation_source import source_excerpt\nclass Service:\n    def data(self):\n        traverse(self._reader, key)\n        return source_excerpt(self._reader, node)"
    assert not violations("atlas.services.navigation", source)


def test_repository_ownership_is_frozen_and_pure_records_are_not_orm() -> None:
    assert REPOSITORY_MODULES == INFRASTRUCTURE | ORM_MODULES | {"atlas.persistence.graph_records"}
    assert REVISIONS == {"atlas.persistence.migrations.versions." + name for name in (
        "0001_initial", "0002_graph_nodes", "0003_graph_relations", "0004_drop_graph_artifact",
    )}
    assert violations("atlas.persistence.graph_records", "session.execute(statement)")


def test_production_modules_respect_database_boundaries() -> None:
    failures = []
    for path in sorted(ROOT.rglob("*.py")):
        found = boundary_violations(module_name(path), path.read_text(encoding="utf-8"), module_package(path))
        if found:
            failures.append(f"{path.relative_to(ROOT)}: {sorted(found)}")
    assert not failures, "\n".join(failures)


def test_policy_helpers_fit_architecture_limits() -> None:
    from tests.test_architecture import control_depth

    for path in (ROOT.parents[1] / "tests").glob("*database_boundar*.py"):
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 600, path
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 100, (path, node.name)
                assert control_depth(node) <= 3, (path, node.name)
