"""AST policy helpers; repository ownership is explicit, never a package exemption."""

import ast
import re
from dataclasses import dataclass
from itertools import chain

from tests.database_boundary_syntax import (
    assignment_pairs,
    belongs_to as belongs_to,
    import_aliases as import_aliases,
    import_targets as import_targets,
    main_config_reflection_ids,
    node_import_aliases as node_import_aliases,
    node_import_targets as node_import_targets,
    propagate_aliases,
    qualified_name as qualified_name,
    resolved_import_module as resolved_import_module,
)

REVISIONS = frozenset({
    "atlas.persistence.migrations.versions.0001_initial",
    "atlas.persistence.migrations.versions.0002_graph_nodes",
    "atlas.persistence.migrations.versions.0003_graph_relations",
    "atlas.persistence.migrations.versions.0004_drop_graph_artifact",
    "atlas.persistence.migrations.versions.0005_mutation_candidates",
})
INFRASTRUCTURE = frozenset({
    "atlas.persistence.database", "atlas.persistence.navigation_database",
    "atlas.persistence.migrations.env",
}) | REVISIONS
ORM_MODULES = frozenset({
    "atlas.persistence.repositories", "atlas.persistence.navigation",
    "atlas.persistence.navigation_queries", "atlas.persistence.graph_queries",
    "atlas.persistence.models",
})
REPOSITORY_MODULES = INFRASTRUCTURE | ORM_MODULES | {"atlas.persistence.graph_records"}
FACTORY = "atlas.services.factories"
FACTORY_IMPORTS = frozenset({
    "atlas.persistence.repositories.repository_store",
    "atlas.persistence.navigation.navigation_reader",
    "atlas.persistence.database.migrate_database",
})
SERVICE_EXPORTS = frozenset({"repository_service", "navigation_service", "migrate_database"})
DB_PACKAGES = ("sqlalchemy", "sqlite3", "aiosqlite", "alembic", "psycopg", "psycopg2", "asyncpg", "pymysql", "MySQLdb", "duckdb")
DB_METHODS = frozenset({
    "execute", "executemany", "executescript", "exec_driver_sql", "query", "scalar", "scalars",
    "commit", "rollback", "flush", "cursor", "connection", "connect", "begin", "begin_nested",
    "create_all", "drop_all", "bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings",
})
DB_CONSTRUCTORS = frozenset({
    "Session", "AsyncSession", "Engine", "AsyncEngine", "Connection", "Query",
    "create_engine", "create_async_engine", "sessionmaker", "async_sessionmaker", "scoped_session",
    "select", "insert", "update", "delete",
})
HANDLES = frozenset({"session", "_session", "connection", "_connection", "engine", "_engine", "cursor", "_cursor"})
SESSION_METHODS = frozenset({"get", "add", "add_all", "delete", "refresh", "merge", "expunge", "expunge_all", "close"})
PORTS = frozenset({"repository", "reader", "_repository", "_reader"})
PORT_TYPES = frozenset({"atlas.domain.repositories.RepositoryProtocol", "atlas.domain.navigation.NavigationReader"})
RAW_EXPRESSIONS = frozenset({"text", "literal_column", "column", "table", "TextClause", "TextualSelect", "ColumnClause", "quoted_name", "custom_op", "DDL", "compiles"})
RAW_OPERATIONS = frozenset({"exec_driver_sql", "executescript", "executemany", "cursor", "from_statement", "op", "bool_op", "prefix_with", "suffix_with"})
SCHEMA_OPERATIONS = frozenset({"create_table", "drop_table", "add_column", "drop_column", "alter_column", "create_index", "drop_index", "create_foreign_key", "create_unique_constraint", "create_check_constraint", "create_primary_key", "drop_constraint", "rename_table"})
REFLECTION = frozenset({"getattr", "setattr", "delattr", "vars", "locals", "globals"})
DYNAMIC = frozenset({"__import__", "eval", "exec", "builtins.__import__", "builtins.eval", "builtins.exec"}) | REFLECTION | {f"builtins.{name}" for name in REFLECTION}
SETUP_SQL = frozenset({"PRAGMA busy_timeout = 30000", "PRAGMA foreign_keys = ON", "PRAGMA journal_mode = WAL", "PRAGMA query_only=ON", "BEGIN", "BEGIN IMMEDIATE"})
SQL = re.compile(r"^\s*(?:--[^\n]*\n\s*)*(?:SELECT\s|WITH\s|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b|(?:CREATE|ALTER|DROP)\s+(?:TABLE|INDEX|VIEW)\b|PRAGMA\s|(?-i:BEGIN|COMMIT|ROLLBACK)\b)", re.I)


def boundary_sensitive(module: str) -> bool:
    """All production packages are guarded, not just the known layers."""
    return belongs_to(module, "atlas")


def node_dynamic_violations(node: ast.AST, aliases: dict[str, str], package: str) -> set[str]:
    violations = {target for target in node_import_targets(node, package) if target.split(".")[0] in {"importlib", "runpy", "pkgutil"} or target in DYNAMIC}
    name = qualified_name(node, aliases)
    if name in DYNAMIC or belongs_to(name, "sys.modules"):
        violations.add(name)
    if reflective_port_extraction(node, aliases):
        violations.add("reflective persistence handle extraction")
    return violations | syntax_dynamic_violations(node)


def syntax_dynamic_violations(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Attribute) and node.attr in {"__dict__", "__getattribute__", "__getattr__", "__setattr__", "__delattr__"}:
        return {f"dynamic reflection {node.attr}"}
    if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
        return {"wildcard import"}
    return set()


def private_reflection_path(node: ast.AST) -> bool:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return True
    return any(part in PORTS | HANDLES | DB_METHODS or part.startswith("_") for part in node.value.split("."))


def reflective_port_extraction(node: ast.AST, aliases: dict[str, str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = qualified_name(node.func, aliases)
    if name == "operator.attrgetter":
        return any(private_reflection_path(arg) for arg in node.args)
    return name == "operator.methodcaller" and bool(node.args) and private_reflection_path(node.args[0])


def dynamic_import_violations(source: str, package: str) -> set[str]:
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    return {violation for node in ast.walk(tree) for violation in node_dynamic_violations(node, aliases, package)}


def forbidden_prefixes(module: str) -> list[str]:
    forbidden: list[str] = []
    if module not in INFRASTRUCTURE:
        forbidden.extend(prefix for prefix in DB_PACKAGES if module not in ORM_MODULES or prefix != "sqlalchemy")
    if module not in REPOSITORY_MODULES and module != FACTORY:
        forbidden.append("atlas.persistence")
    return forbidden + layer_prefixes(module)


def layer_prefixes(module: str) -> list[str]:
    rules = (("atlas.services", "atlas.cli"), ("atlas.domain", "atlas.cli"),
             ("atlas.domain", "atlas.services"), ("atlas.persistence", "atlas.cli"),
             ("atlas.persistence", "atlas.services"))
    return (["atlas.bootstrap"] if not belongs_to(module, "atlas.cli") else []) + [
        target for layer, target in rules if belongs_to(module, layer)]


def matches_forbidden_prefix(target: str, forbidden: list[str]) -> bool:
    return any(belongs_to(target, prefix) for prefix in forbidden)


def forbidden_imports(module: str, targets: set[str]) -> set[str]:
    forbidden = {target for target in targets if matches_forbidden_prefix(target, forbidden_prefixes(module))}
    if module not in REPOSITORY_MODULES and not belongs_to(module, "atlas.services"):
        forbidden.update(target for target in targets if target in PORT_TYPES)
    return forbidden | factory_targets_forbidden(module, targets)


def factory_targets_forbidden(module: str, targets: set[str]) -> set[str]:
    if module == FACTORY:
        allowed = FACTORY_IMPORTS | {name.rsplit(".", 1)[0] for name in FACTORY_IMPORTS}
        return unapproved_targets(targets, "atlas.persistence", allowed)
    exports = {FACTORY} | {f"{FACTORY}.{name}" for name in SERVICE_EXPORTS}
    return unapproved_targets(targets, FACTORY, exports)


def unapproved_targets(targets: set[str], prefix: str, allowed: set[str] | frozenset[str]) -> set[str]:
    return {target for target in targets if belongs_to(target, prefix) and target not in allowed}


def bootstrap_violations(tree: ast.Module, package: str) -> set[str]:
    """Bootstrap is a compatibility re-export, not another composition root."""
    return {f"bootstrap must only re-export service factories (line {node.lineno})" for node in tree.body if not bootstrap_statement_allowed(node, package)}


def bootstrap_statement_allowed(node: ast.AST, package: str) -> bool:
    if isinstance(node, ast.Expr):
        return isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, ast.ImportFrom):
        return resolved_import_module(node, package) == FACTORY and all(bootstrap_export_allowed(alias) for alias in node.names)
    if isinstance(node, ast.Assign):
        return bootstrap_assignment_allowed(node)
    return False


def bootstrap_assignment_allowed(node: ast.Assign) -> bool:
    return all(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets) and bootstrap_all_allowed(node.value)


def bootstrap_export_allowed(alias: ast.alias) -> bool:
    return alias.name in SERVICE_EXPORTS and alias.asname in {None, alias.name}


def bootstrap_all_allowed(value: ast.AST) -> bool:
    return isinstance(value, (ast.List, ast.Tuple)) and all(isinstance(item, ast.Constant) and item.value in SERVICE_EXPORTS for item in value.elts)


def factory_import_violations(tree: ast.AST, package: str) -> set[str]:
    return set().union(*(factory_node_import_violations(node, package) for node in ast.walk(tree)))


def factory_node_import_violations(node: ast.AST, package: str) -> set[str]:
    if not any(belongs_to(target, "atlas.persistence") for target in node_import_targets(node, package)):
        return set()
    imported = node_import_aliases(node, package).values()
    if not isinstance(node, ast.ImportFrom) or any(target not in FACTORY_IMPORTS for target in imported):
        return {"factory imports must name only repository contexts or migration operation"}
    if any(not private_import_alias(alias) for alias in node.names):
        return {"factory persistence operations must be imported privately"}
    return set()


def private_import_alias(alias: ast.alias) -> bool:
    return bool(alias.asname) and str(alias.asname).startswith("_")


def in_memory_repository_attributes(tree: ast.AST, aliases: dict[str, str]) -> set[int]:
    """ParsedRepository is a domain graph, not a persistence implementation."""
    allowed: set[int] = set()
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            allowed.update(in_memory_function_attributes(function, aliases))
    return allowed


def in_memory_function_attributes(function: ast.FunctionDef | ast.AsyncFunctionDef, aliases: dict[str, str]) -> set[int]:
    parameters = {arg.arg for arg in function.args.args if arg.annotation and qualified_name(arg.annotation, aliases) == "atlas.domain.models.ParsedRepository"}
    if not parameters:
        return set()
    pairs = chain.from_iterable(map(assignment_pairs, ast.walk(function)))
    return {id(target) for target, value in pairs if in_memory_assignment(target, value, parameters)}


def in_memory_assignment(target: ast.AST, value: ast.AST, parameters: set[str]) -> bool:
    return isinstance(target, ast.Attribute) and target.attr == "repository" and isinstance(value, ast.Name) and value.id in parameters


def raw_sql_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    name = qualified_name(node, aliases)
    function = qualified_name(node.func, aliases) if isinstance(node, ast.Call) else ""
    if raw_expression(name, function):
        return {f"raw SQL/driver access {name}"}
    return raw_literal_violations(node, function)


def raw_expression(name: str, function: str) -> bool:
    textual = function in RAW_EXPRESSIONS or belongs_to(name or function, "sqlalchemy") and (name or function).rsplit(".", 1)[-1] in RAW_EXPRESSIONS
    return textual or name != "alembic.op" and name.rsplit(".", 1)[-1] in RAW_OPERATIONS | {"is_literal"}


def raw_literal_violations(node: ast.AST, function: str) -> set[str]:
    if isinstance(node, ast.keyword) and node.arg == "is_literal":
        return {"raw literal expression flag"}
    if raw_string_execution(node, function):
        return {"raw SQL execution"}
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL.match(node.value):
        return {"raw SQL statement"}
    return set()


def raw_string_execution(node: ast.AST, function: str) -> bool:
    return isinstance(node, ast.Call) and function.rsplit(".", 1)[-1] in {"execute", "scalar", "scalars"} and bool(node.args) and string_expression(node.args[0])


def string_expression(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr) or isinstance(node, ast.Constant) and isinstance(node.value, str)


def setup_statement(node: ast.AST) -> bool:
    if isinstance(node, ast.IfExp):
        return setup_statement(node.body) and setup_statement(node.orelse)
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in SETUP_SQL


def infrastructure_sql_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Infrastructure driver SQL is literal setup only, never domain queries."""
    name = qualified_name(node.func, aliases) if isinstance(node, ast.Call) else qualified_name(node, aliases)
    method = name.rsplit(".", 1)[-1]
    domain = infrastructure_domain_violations(node, name)
    if domain:
        return domain
    if isinstance(node, ast.Call) and method in {"execute", "exec_driver_sql", "executemany", "executescript", "scalar", "scalars"}:
        return infrastructure_execution_violations(node, name)
    if literal_setup(node):
        return set()
    found = raw_sql_violations(node, aliases)
    if method in {"execute", "exec_driver_sql", "cursor"}:
        return set()
    return found


def literal_setup(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in SETUP_SQL


def infrastructure_domain_violations(node: ast.AST, name: str) -> set[str]:
    method = name.rsplit(".", 1)[-1]
    if method in {"query", "select", "insert", "update", "delete", "bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings", "flush", "commit", "create_all", "drop_all"} or belongs_to(name, "sqlalchemy") and method in {"Query", "Select", "Insert", "Update", "Delete"}:
        return {f"infrastructure cannot build domain queries: {name}"}
    if isinstance(node, ast.Call) and method in SESSION_METHODS - {"close", "expunge", "expunge_all"}:
        if method != "get" or name.rsplit(".", 1)[0] not in {"os.environ", "alembic.context.config.attributes", "connection.info"}:
            return {f"infrastructure cannot access domain rows: {name}"}
    return set()


def infrastructure_execution_violations(node: ast.Call, name: str) -> set[str]:
    if name.rsplit(".", 1)[-1] in {"execute", "exec_driver_sql"} and len(node.args) == 1 and not node.keywords and setup_statement(node.args[0]):
        return set()
    return {f"infrastructure SQL must be literal setup only: {name}"}


def migration_schema_text(tree: ast.AST, module: str, aliases: dict[str, str]) -> set[int]:
    """Frozen revision's collation expression is schema DDL, not a text-query allowance."""
    if module != "atlas.persistence.migrations.versions.0002_graph_nodes":
        return set()
    return set().union(*(migration_index_text(node, aliases) for node in ast.walk(tree)))


def migration_index_text(node: ast.AST, aliases: dict[str, str]) -> set[int]:
    match node:
        case ast.Call(func=operation, args=[
            ast.Constant(value="graph_nodes_name"), ast.Constant(value="graph_nodes"),
            ast.List(elts=[ast.Constant(value="repository_id"), ast.Call() as expression]),
        ], keywords=[]):
            expected = ast.Call(func=expression.func, args=[ast.Constant(value="name COLLATE NOCASE")], keywords=[])
            if qualified_name(operation, aliases) == "alembic.op.create_index" and qualified_name(expression.func, aliases) == "sqlalchemy.text" and ast.dump(expression) == ast.dump(expected):
                return {id(child) for child in ast.walk(expression)}
    return set()


def migration_sql_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    name = qualified_name(node.func, aliases) if isinstance(node, ast.Call) else qualified_name(node, aliases)
    method = name.rsplit(".", 1)[-1]
    if name.startswith("alembic.op.") and method not in SCHEMA_OPERATIONS:
        return {f"migration operation must be schema DDL: {name}"}
    if method in DB_METHODS | DB_CONSTRUCTORS | SESSION_METHODS or method in {"get_bind", "bulk_insert"}:
        return {f"migration cannot query or mutate domain data: {name}"}
    return raw_sql_violations(node, aliases)


def factory_escape_violations(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    aliases = dict(aliases)
    for node in ast.walk(tree):
        aliases.update(context_port_aliases(node))
    aliases = port_aliases(tree, aliases)
    return set().union(*(return_port_violations(node, aliases) for node in ast.walk(tree)))


def context_port_aliases(node: ast.AST) -> dict[str, str]:
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return {child.id: "self._repository" for child in ast.walk(node.optional_vars) if isinstance(child, ast.Name)}
    return {}


def return_port_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    if isinstance(node, (ast.Return, ast.Yield)) and node.value is not None:
        return port_escape_violations(node.value, aliases)
    return set()


def database_behavior_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    name = qualified_name(node.func, aliases) if isinstance(node, ast.Call) else qualified_name(node, aliases)
    method = name.rsplit(".", 1)[-1]
    operation = database_operation(name, method)
    if isinstance(node, ast.Attribute) and operation:
        return {f"database handle/operation {name}"}
    if isinstance(node, ast.Call) and (operation or name in DB_CONSTRUCTORS):
        return {f"database operation {name}"}
    return set()


def database_operation(name: str, method: str) -> bool:
    receiver = name.rsplit(".", 1)[0].rsplit(".", 1)[-1] if "." in name else ""
    return method in DB_METHODS | HANDLES or receiver in HANDLES and method in SESSION_METHODS


def service_port_violations(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    aliases = port_aliases(tree, aliases)
    return set().union(*(service_node_port_violations(node, aliases) for node in ast.walk(tree)))


def service_node_port_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    violations = return_port_violations(node, aliases)
    if isinstance(node, ast.Call):
        violations.update(port_argument_violations(node, aliases))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__":
        violations.update(service_constructor_violations(node, aliases))
    for target, value in assignment_pairs(node):
        if isinstance(target, ast.Attribute) and ast.unparse(target) not in {"self._repository", "self._reader"}:
            violations.update(port_escape_violations(value, aliases))
    return violations


def port_aliases(tree: ast.AST, aliases: dict[str, str]) -> dict[str, str]:
    aliases = dict(aliases)
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation and port_annotation(node.annotation, aliases):
            aliases[node.arg] = "self._repository"
    pairs = list(chain.from_iterable(map(assignment_pairs, ast.walk(tree))))
    return propagate_aliases(aliases, pairs, port_assignment_aliases)


def annotation_expression(node: ast.AST) -> ast.AST:
    return ast.parse(node.value, mode="eval").body if isinstance(node, ast.Constant) and isinstance(node.value, str) else node


def port_annotation(node: ast.AST, aliases: dict[str, str]) -> bool:
    node = annotation_expression(node)
    return any(qualified_name(child, aliases) in PORT_TYPES for child in ast.walk(node))


def port_assignment_aliases(target: ast.AST, value: ast.AST, aliases: dict[str, str]) -> dict[str, str]:
    if not port_escape_violations(value, aliases):
        return {}
    if isinstance(target, ast.Attribute):
        return {qualified_name(target, aliases): "self._repository"}
    return {child.id: "self._repository" for child in ast.walk(target) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}


def port_argument_violations(call: ast.Call, aliases: dict[str, str]) -> set[str]:
    name = qualified_name(call.func, aliases)
    if belongs_to(name, "atlas.services") or belongs_to(name, "self"):
        return set()
    values = [*call.args, *(keyword.value for keyword in call.keywords)]
    return {violation for value in values for violation in port_escape_violations(value, aliases)}


def port_escape_violations(value: ast.AST, aliases: dict[str, str]) -> set[str]:
    if isinstance(value, ast.Call) and qualified_name(value.func, aliases) not in {"getattr", "builtins.getattr"}:
        return set()
    name = qualified_name(value, aliases)
    if any(belongs_to(name, f"self.{port}") for port in PORTS):
        return {f"service leaks private dependency {name}"}
    return {violation for child in ast.iter_child_nodes(value) for violation in port_escape_violations(child, aliases)}


def service_constructor_violations(function: ast.FunctionDef | ast.AsyncFunctionDef, aliases: dict[str, str]) -> set[str]:
    protocols = {"_repository": "atlas.domain.repositories.RepositoryProtocol", "_reader": "atlas.domain.navigation.NavigationReader"}
    parameters = {arg.arg: arg.annotation for arg in function.args.args}
    violations: set[str] = set()
    pairs = list(chain.from_iterable(map(assignment_pairs, ast.walk(function))))
    parameters = propagate_aliases(parameters, pairs, parameter_assignment_aliases)
    for target, value in pairs:
        if not isinstance(target, ast.Attribute) or target.attr not in protocols:
            continue
        annotation = parameters.get(value.id) if isinstance(value, ast.Name) else None
        if not constructor_protocol_matches(annotation, aliases, protocols[target.attr]):
            violations.add(f"service {target.attr} must accept a domain protocol")
    return violations


def parameter_assignment_aliases(target, value, parameters):
    if isinstance(target, ast.Name) and isinstance(value, ast.Name) and value.id in parameters:
        return {target.id: parameters[value.id]}
    return {}


def constructor_protocol_matches(annotation, aliases, protocol):
    return annotation is not None and qualified_name(annotation_expression(annotation), aliases) == protocol


@dataclass
class BoundaryState:
    module: str
    aliases: dict[str, str]
    in_memory: set[int]
    memory_owners: set[str]
    docstrings: set[int]
    migration_text: set[int]


def port_access_violations(node: ast.AST, state: BoundaryState) -> set[str]:
    module = state.module
    if isinstance(node, ast.Call):
        name = qualified_name(node, {})
        port = name.rsplit(".", 1)[-1]
        if port in PORTS and not (belongs_to(module, "atlas.services") and name in {"self._reader", "self._repository"}):
            return {f"repository/reader handle access {name}"}
    if not isinstance(node, ast.Attribute) or node.attr not in PORTS:
        return set()
    if port_attribute_allowed(node, state):
        return set()
    return {f"repository/reader handle access {ast.unparse(node)}"}


def port_attribute_allowed(node: ast.Attribute, state: BoundaryState) -> bool:
    if belongs_to(state.module, "atlas.services"):
        return node.attr.startswith("_") and isinstance(node.value, ast.Name) and node.value.id == "self"
    return id(node) in state.in_memory or ast.unparse(node) in state.memory_owners and isinstance(node.ctx, ast.Load)


def boundary_violations(module: str, source: str, package: str) -> set[str]:
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    violations = forbidden_imports(module, import_targets(source, package)) | guarded_dynamic_violations(tree, aliases, (module, package))
    if module == "atlas.bootstrap":
        violations.update(bootstrap_violations(tree, package))
    if module == FACTORY:
        violations.update(factory_import_violations(tree, package))
        violations.update(factory_escape_violations(tree, aliases))
    if belongs_to(module, "atlas.services"):
        violations.update(service_port_violations(tree, aliases))
    in_memory = in_memory_repository_attributes(tree, aliases)
    memory_owners = {ast.unparse(node) for node in ast.walk(tree) if id(node) in in_memory}
    migration_text = migration_schema_text(tree, module, aliases)
    docstrings = docstring_ids(tree)
    state = BoundaryState(module, aliases, in_memory, memory_owners, docstrings, migration_text)
    return violations | set().union(*(boundary_node_violations(node, state) for node in ast.walk(tree)))


def docstring_ids(tree: ast.AST) -> set[int]:
    statements = (node.body[0] for node in ast.walk(tree) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and has_docstring(node))
    return {id(node.value) for node in statements if isinstance(node, ast.Expr)}


def has_docstring(node) -> bool:
    return isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and bool(node.body) and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)


def boundary_node_violations(node: ast.AST, state: BoundaryState) -> set[str]:
    violations = boundary_sql_violations(node, state)
    if state.module not in INFRASTRUCTURE | ORM_MODULES:
        violations.update(database_behavior_violations(node, state.aliases))
    if state.module not in REPOSITORY_MODULES:
        violations.update(port_access_violations(node, state))
    return violations


def boundary_sql_violations(node: ast.AST, state: BoundaryState) -> set[str]:
    if id(node) in state.docstrings:
        return set()
    if state.module in REVISIONS:
        return set() if id(node) in state.migration_text else migration_sql_violations(node, state.aliases)
    if state.module in INFRASTRUCTURE:
        return infrastructure_sql_violations(node, state.aliases)
    return raw_sql_violations(node, state.aliases)


def guarded_dynamic_violations(tree: ast.AST, aliases: dict[str, str], location: tuple[str, str]) -> set[str]:
    module, package = location
    allowed = main_config_reflection_ids(tree, aliases) if module == "atlas.metrics.check" else set()
    nodes = (node for node in ast.walk(tree) if id(node) not in allowed)
    return set().union(*(node_dynamic_violations(node, aliases, package) for node in nodes))
