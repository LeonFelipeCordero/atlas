"""Alembic revisions freeze literal schema and SQL, independent of runtime models."""

import ast
import re
import sys

import pytest

from tests.test_architecture import ROOT, module_package
from tests.test_database_boundaries import (
    dynamic_import_violations,
    import_aliases,
    node_import_targets,
    qualified_name,
)

VERSIONS = ROOT / "persistence" / "migrations" / "versions"
DDL_OPERATIONS = {
    "create_table", "drop_table", "create_index", "drop_index", "add_column",
    "drop_column", "alter_column", "create_primary_key", "create_foreign_key",
    "create_unique_constraint", "create_check_constraint", "drop_constraint",
    "rename_table", "batch_alter_table",
}
SCHEMA_CONSTRUCTORS = {
    "Column", "ForeignKey", "ForeignKeyConstraint", "PrimaryKeyConstraint",
    "UniqueConstraint", "CheckConstraint", "Index", "Table",
}
TABLE_CONSTRAINTS = {
    "Column", "ForeignKeyConstraint", "PrimaryKeyConstraint", "UniqueConstraint",
    "CheckConstraint",
}


def literal_string(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def literal_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(literal_value(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return literal_dictionary(node)
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and literal_value(node.operand)


def literal_dictionary(node: ast.Dict) -> bool:
    return all(key is not None and literal_value(key) for key in node.keys) and all(
        literal_value(value) for value in node.values
    )


def string_list(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple)) and all(literal_string(item) for item in node.elts)


def sqlalchemy_expression(node: ast.AST, aliases: dict[str, str]) -> bool:
    """Types, defaults, and SQL expressions may use SQLAlchemy, not local factories."""
    name = qualified_name(node, aliases)
    if literal_value(node) or name.startswith("sqlalchemy."):
        return True
    if not isinstance(node, ast.Call):
        return False
    return qualified_name(node.func, aliases).startswith("sqlalchemy.") and sqlalchemy_arguments(node, aliases)


def sqlalchemy_arguments(call: ast.Call, aliases: dict[str, str]) -> bool:
    return all(sqlalchemy_expression(arg, aliases) for arg in call.args) and all(
        keyword.arg is not None and sqlalchemy_expression(keyword.value, aliases) for keyword in call.keywords
    )


def table_bindings(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    """0001 uses a local Table solely to build its lower(name) unique index."""
    tables = set()
    for node in ast.walk(tree):
        tables.update(node_table_bindings(node, aliases))
    return tables


def node_table_bindings(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        return set()
    if qualified_name(node.value.func, aliases) != "sqlalchemy.Table":
        return set()
    return {target.id for target in node.targets if isinstance(target, ast.Name)}


def index_expression(node: ast.AST, aliases: dict[str, str], tables: set[str]) -> bool:
    name = qualified_name(node, aliases)
    if literal_string(node):
        return True
    if isinstance(node, ast.Attribute) and any(name.startswith(f"{table}.c.") for table in tables):
        return True
    return isinstance(node, ast.Call) and literal_index_call(node, aliases, tables)


def literal_index_call(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> bool:
    if qualified_name(call.func, aliases) == "sqlalchemy.text":
        return literal_sql(call, aliases)
    return qualified_name(call.func, aliases).startswith("sqlalchemy.func.") and all(
        index_expression(arg, aliases, tables) for arg in call.args
    ) and not call.keywords


def schema_call_violations(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> set[str]:
    name = qualified_name(call.func, aliases).rsplit(".", 1)[-1]
    first_literal = string_list if name == "ForeignKeyConstraint" else literal_string
    checks = {
        f"{name} requires a literal name/column": bool(call.args) and first_literal(call.args[0]),
        f"{name} uses nonliteral options": all(literal_schema_option(key, aliases) for key in call.keywords),
        f"{name} uses schema factories": schema_arguments_literal(call, aliases, tables),
    }
    return {message for message, valid in checks.items() if not valid}


def schema_arguments_literal(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> bool:
    name = qualified_name(call.func, aliases).rsplit(".", 1)[-1]
    if name in {"Column", "Table"}:
        return all(sqlalchemy_expression(arg, aliases) for arg in call.args[1:])
    if name in {"ForeignKeyConstraint", "PrimaryKeyConstraint", "UniqueConstraint", "CheckConstraint"}:
        return all(literal_column_argument(arg) for arg in call.args)
    if name == "Index":
        return all(index_expression(arg, aliases, tables) for arg in call.args[1:])
    return all(literal_string(arg) for arg in call.args)


def literal_column_argument(node: ast.AST) -> bool:
    return literal_string(node) or string_list(node)


def ddl_call_violations(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> set[str]:
    operation = qualified_name(call.func, aliases).rsplit(".", 1)[-1]
    checks = {
        f"{operation} requires a literal name": bool(call.args) and literal_string(call.args[0]),
        f"{operation} uses nonliteral options": all(literal_schema_option(key, aliases) for key in call.keywords),
        f"{operation} requires inline literal schema": ddl_arguments_literal(call, aliases, tables),
    }
    return {message for message, valid in checks.items() if not valid}


def inline_schema_call(node: ast.AST, aliases: dict[str, str], constructors: set[str]) -> bool:
    return isinstance(node, ast.Call) and qualified_name(node.func, aliases) in {
        f"sqlalchemy.{constructor}" for constructor in constructors
    }


def ddl_arguments_literal(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> bool:
    operation = qualified_name(call.func, aliases).rsplit(".", 1)[-1]
    if operation == "create_table":
        return all(inline_schema_call(arg, aliases, TABLE_CONSTRAINTS) for arg in call.args[1:])
    if operation == "add_column":
        return len(call.args) == 2 and inline_schema_call(call.args[1], aliases, {"Column"})
    if operation == "create_index":
        return literal_index_arguments(call, aliases, tables)
    return all(literal_string(arg) or string_list(arg) for arg in call.args[1:])


def literal_index_arguments(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> bool:
    if len(call.args) != 3 or not literal_string(call.args[1]):
        return False
    columns = call.args[2]
    return isinstance(columns, (ast.List, ast.Tuple)) and all(
        index_expression(arg, aliases, tables) for arg in columns.elts
    )


def literal_schema_option(keyword: ast.keyword, aliases: dict[str, str]) -> bool:
    if keyword.arg in {"name", "table_name", "column_name", "constraint_name", "schema", "referent_schema"}:
        return literal_string(keyword.value) or isinstance(keyword.value, ast.Constant) and keyword.value.value is None
    return keyword.arg is not None and sqlalchemy_expression(keyword.value, aliases)


def literal_sql(node: ast.AST, aliases: dict[str, str]) -> bool:
    if literal_string(node):
        return True
    return (
        isinstance(node, ast.Call)
        and qualified_name(node.func, aliases) == "sqlalchemy.text"
        and len(node.args) == 1
        and literal_string(node.args[0])
        and not node.keywords
    )


def revision_import_violations(tree: ast.AST, package: str) -> set[str]:
    allowed = sys.stdlib_module_names | {"sqlalchemy", "alembic"}
    return {
        target
        for node in ast.walk(tree)
        for target in node_import_targets(node, package)
        if target.split(".")[0] not in allowed
    }


def migration_violations(source: str, package: str = "atlas.persistence.migrations.versions") -> set[str]:
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    tables = table_bindings(tree, aliases)
    violations = revision_import_violations(tree, package) | dynamic_import_violations(source, package)
    entrypoints = {
        id(node) for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"upgrade", "downgrade"}
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.comprehension)):
            violations.add("revision uses a schema/data loop or registry iteration")
        if isinstance(node, ast.Call):
            violations.update(revision_call_violations(node, aliases, tables))
        if hides_schema_helper(node, aliases, entrypoints):
            violations.add("revision hides DDL in a helper function")
    violations.update(ddl_reference_violations(tree, aliases))
    return violations


def hides_schema_helper(node: ast.AST, aliases: dict[str, str], entrypoints: set[int]) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) or id(node) in entrypoints:
        return False
    return any(is_schema_building_call(child, aliases) for child in ast.walk(node))


def revision_call_violations(call: ast.Call, aliases: dict[str, str], tables: set[str]) -> set[str]:
    name = qualified_name(call.func, aliases)
    violations = set()
    if name.removeprefix("sqlalchemy.") in SCHEMA_CONSTRUCTORS:
        violations.update(schema_call_violations(call, aliases, tables))
    if name.startswith("alembic.op.") and name.rsplit(".", 1)[-1] in DDL_OPERATIONS:
        violations.update(ddl_call_violations(call, aliases, tables))
    method = call.func.attr if isinstance(call.func, ast.Attribute) else name.rsplit(".", 1)[-1]
    if method in {"create_all", "drop_all"}:
        violations.add("revision uses live metadata DDL")
    if is_table_ddl(method, name, tables):
        violations.add("revision bypasses Alembic with Table DDL")
    violations.update(sql_execution_violations(call, aliases, method))
    return violations


def is_table_ddl(method: str, name: str, tables: set[str]) -> bool:
    return method in {"create", "drop"} and any(name.startswith(f"{table}.") for table in tables)


def has_schema_ddl(sql: str) -> bool:
    # Ignore quoted SQL values/identifiers and comments, not just leading whitespace.
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]", " ", sql, flags=re.DOTALL)
    return bool(re.search(r"(?:^|;)\s*(?:CREATE|ALTER|DROP|TRUNCATE)\b", cleaned, flags=re.IGNORECASE))


def sql_execution_violations(call: ast.Call, aliases: dict[str, str], method: str) -> set[str]:
    if method not in {"execute", "executemany", "executescript", "exec_driver_sql", "scalar"}:
        return set()
    if not call.args:
        return set() if method == "scalar" else {"revision executes SQL without a literal"}
    if not literal_sql(call.args[0], aliases):
        return {"revision executes nonliteral SQL"}
    sql = call.args[0]
    if isinstance(sql, ast.Call):
        sql = sql.args[0]
    assert isinstance(sql, ast.Constant) and isinstance(sql.value, str)
    if has_schema_ddl(sql.value):
        return {"revision uses SQL DDL instead of inline Alembic schema calls"}
    return set()


def is_schema_building_call(node: ast.AST, aliases: dict[str, str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = qualified_name(node.func, aliases)
    return (
        name.startswith("alembic.op.") and name.rsplit(".", 1)[-1] in DDL_OPERATIONS
        or name in {f"sqlalchemy.{constructor}" for constructor in SCHEMA_CONSTRUCTORS}
    )


def ddl_reference_violations(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    callees = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    return {
        "revision aliases/registers a DDL operation"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Attribute, ast.Name))
        and qualified_name(node, aliases).startswith("alembic.op.")
        and qualified_name(node, aliases).rsplit(".", 1)[-1] in DDL_OPERATIONS
        and id(node) not in callees
    }


@pytest.mark.parametrize("source", [
    "from atlas.persistence.models import Base",
    "from ... import models as entities",
    "def upgrade():\n    from atlas.persistence.database import create_engine",
    "from typing import TYPE_CHECKING as TC\nif TC:\n    from atlas.domain.models import Graph",
    "import atlas.persistence.models as entities",
    "from atlas import persistence",
    "import importlib as loader\nloader.import_module('atlas.persistence.models')",
])
def test_revisions_cannot_import_runtime_schema_or_dynamic_loaders(source: str) -> None:
    assert migration_violations(source)


@pytest.mark.parametrize("body", [
    "op.create_table(table_name, Column('id', Integer))",
    "op.create_table('rows', Column(column_name, Integer))",
    "op.create_table('rows', *columns())",
    "op.create_table('rows', columns())",
    "op.create_table('rows', Column('id', column_type()))",
    "op.create_table('rows', Column('id', Integer, **options))",
    "op.create_table('rows', Column('id', Integer), UniqueConstraint(column_name))",
    "op.create_table('rows', ForeignKeyConstraint(local_columns, ['other.id']))",
    "op.create_index(index_name, 'rows', ['id'])",
    "op.create_index('rows_id', table_name, ['id'])",
    "op.create_index('rows_id', 'rows', columns())",
    "op.create_index('rows_id', 'rows', [column_factory()])",
    "op.drop_index('rows_id', table_name=table_name)",
    "op.drop_index('rows_id', table_name=text('rows'))",
    "op.create_table('rows', Column('id', Integer), UniqueConstraint('id', name=text('rows_unique')))",
    "op.drop_table(table_name)",
    "op.add_column('rows', column_factory())",
    "op.drop_column('rows', column_name)",
    "op.create_unique_constraint('unique_name', 'rows', columns)",
    "Base.metadata.create_all(bind)",
    "metadata.drop_all(bind)",
    "op.execute(sql)",
    "op.execute(text(sql))",
    "op.execute(f'INSERT INTO {table_name} VALUES (1)')",
    "op.get_bind().execute(text(sql))",
    "op.get_bind().scalar(text(sql))",
    "op.execute('INSERT ' + 'INTO rows VALUES (1)')",
])
def test_revisions_require_literal_schema_and_sql(body: str) -> None:
    source = f"from alembic import op\nfrom sqlalchemy import Column, Integer, UniqueConstraint, ForeignKeyConstraint, text\ndef upgrade():\n    {body}\n"
    assert migration_violations(source)


@pytest.mark.parametrize("source", [
    "def make_table():\n    op.create_table('rows', Column('id', Integer))\ndef upgrade():\n    make_table()",
    "def upgrade():\n    def create():\n        op.create_table('rows', Column('id', Integer))\n    create()",
    "def upgrade():\n    for name in ['a', 'b']:\n        op.create_table(name, Column('id', Integer))",
    "def upgrade():\n    [op.create_table(name, Column('id', Integer)) for name in names]",
    "SCHEMA = {'rows': op.create_table}\ndef upgrade():\n    SCHEMA['rows']('rows', Column('id', Integer))",
    "create = op.create_table\ndef upgrade():\n    create('rows', Column('id', Integer))",
    "def columns():\n    return Column('id', Integer)",
    "def upgrade():\n    def downgrade():\n        op.drop_table('rows')",
])
def test_ddl_cannot_be_hidden_in_helpers_loops_or_registries(source: str) -> None:
    assert migration_violations(f"from alembic import op\nfrom sqlalchemy import Column, Integer\n{source}")


@pytest.mark.parametrize("source", [
    """from alembic import op as operations
import sqlalchemy as sa
revision = '0002_graph_nodes'
down_revision = '0001_initial'
def upgrade():
    operations.create_table('nodes', sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('repository_id', sa.Text, sa.ForeignKey('repositories.id', ondelete='CASCADE')),
        sa.UniqueConstraint('repository_id', 'id', name='nodes_unique'))
    operations.create_index('nodes_repository', 'nodes', ['repository_id'])
    operations.create_index('nodes_name', 'nodes', [sa.text('name COLLATE NOCASE')])
def downgrade():
    operations.drop_index('nodes_repository', table_name='nodes')
    operations.drop_table('nodes')
""",
    """from alembic import op
from sqlalchemy import Column, ForeignKeyConstraint, Integer, String

def upgrade():
    op.create_table('nodes', Column('id', Integer), Column('name', String(255)),
        ForeignKeyConstraint(['id'], ['other.id'], name='nodes_fk', ondelete='CASCADE'))
""",
    """from alembic import op
from sqlalchemy import Column, Index, MetaData, Table, Text, func

def upgrade():
    rows = Table('rows', MetaData(), Column('name', Text))
    op.create_index('rows_name_unique', 'rows', [func.lower(rows.c.name)], unique=True)
""",
    """from alembic import op
from sqlalchemy import text

def upgrade():
    op.execute('INSERT INTO nodes SELECT * FROM old_nodes')
    connection = op.get_bind()
    connection.execute(text('INSERT INTO relations SELECT * FROM old_relations'))
    if connection.scalar(text('SELECT count(*) FROM invalid_cycles')):
        raise ValueError('invalid cycle')
    count = op.get_bind().execute(text('SELECT count(*) FROM nodes')).scalar()
""",
    "from alembic import op\nop.execute('SELECT importlib, atlas, sqlalchemy FROM legacy')",
])
def test_literal_orm_ddl_and_data_sql_styles_are_allowed(source: str) -> None:
    assert not migration_violations(source)


@pytest.mark.parametrize("source", [
    "from alembic.op import execute as run\nrun(sql)",
    "from alembic.op import execute as run\nfrom sqlalchemy import text as statement\nrun(statement(sql))",
    "from sqlalchemy import Table, MetaData, Column, Integer\nrows = Table('rows', MetaData(), Column('id', Integer))\nrows.create(bind)",
])
def test_aliases_cannot_bypass_literal_sql_or_alembic_ddl(source: str) -> None:
    assert migration_violations(source)


@pytest.mark.parametrize("sql", [
    "CREATE TABLE sneaky (id INTEGER)",
    "/* frozen? */ CREATE INDEX sneaky ON rows(id)",
    "-- comment\nALTER TABLE rows ADD COLUMN hidden INTEGER",
    "DROP TABLE rows", "SELECT 1; CREATE TABLE sneaky (id INTEGER)",
])
def test_schema_ddl_cannot_hide_in_literal_sql(sql: str) -> None:
    source = f"from alembic import op\nfrom sqlalchemy import text\ndef upgrade():\n    op.get_bind().execute(text({sql!r}))"
    assert migration_violations(source)


@pytest.mark.parametrize("sql", [
    "SELECT 'CREATE TABLE hidden (id INTEGER)'",
    "INSERT INTO rows VALUES ('message; DROP TABLE hidden')",
    "/* CREATE TABLE hidden */ UPDATE rows SET value='ALTER TABLE hidden'",
])
def test_ddl_words_in_data_values_and_comments_are_allowed(sql: str) -> None:
    assert not migration_violations(f"from alembic import op\nop.execute({sql!r})")


def test_alias_of_execute_with_literal_sql_is_allowed() -> None:
    assert not migration_violations("from alembic.op import execute as run\nrun('DELETE FROM rows')")


def test_initial_literal_revision_preserves_local_table_expression_style() -> None:
    path = VERSIONS / "0001_initial.py"
    assert path.is_file()
    assert not migration_violations(path.read_text(encoding="utf-8"), module_package(path))


def test_all_production_revisions_are_self_contained_and_literal() -> None:
    paths = sorted(VERSIONS.glob("*.py"))
    assert paths, "Alembic revisions must exist"
    for path in paths:
        if path.name == "__init__.py":
            continue
        violations = migration_violations(path.read_text(encoding="utf-8"), module_package(path))
        assert not violations, f"{path.relative_to(ROOT)} violates literal migration boundaries: {sorted(violations)}"


def test_migration_environment_may_import_runtime_metadata() -> None:
    path = ROOT / "persistence" / "migrations" / "env.py"
    assert path.is_file()
    # env.py configures Alembic; unlike frozen versions it may use Base.metadata.
    assert path.parent != VERSIONS
    source = path.read_text(encoding="utf-8")
    assert not dynamic_import_violations(source, module_package(path))


def test_fixture_revision_cannot_import_metadata_but_environment_is_separate() -> None:
    source = "from atlas.persistence.models import Base\ntarget_metadata = Base.metadata"
    assert migration_violations(source)
    assert not dynamic_import_violations(source, "atlas.persistence.migrations")
