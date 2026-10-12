"""Policy contracts over coherent coffee service and storage variants."""

import ast
from pathlib import Path

import pytest

from tests.database_boundary_policy import (
    boundary_violations,
    dynamic_import_violations,
    node_dynamic_violations,
)
from tests.database_boundary_syntax import import_aliases, import_targets
from tests.test_architecture import module_dependencies
from tests.test_persistence_entity_boundaries import entity_violations, graph_record_violations

VARIANTS = Path(__file__).parent / "fixtures/variants/policy"
SERVICE = "atlas.services.orders"
FACTORY = "atlas.services.factories"
DATABASE = "atlas.persistence.database"
REPOSITORY = "atlas.persistence.repositories"
REVISION = "atlas.persistence.migrations.versions.0002_graph_nodes"


def source(project: str, filename: str) -> str:
    return (VARIANTS / project / filename).read_text(encoding="utf-8")


def selected_source(project: str, filename: str, *functions: str) -> str:
    """Retain a module's imports/schema/constructors and the selected operations.

    Each unsafe operation is checked independently, so one violation cannot mask
    another. The complete modules also feed the generic variant snapshots.
    """
    tree = ast.parse(source(project, filename))
    tree.body = [project_definition(node, functions) for node in tree.body if keep_definition(node, functions)]
    return ast.unparse(tree)


def keep_definition(node: ast.AST, functions: tuple[str, ...]) -> bool:
    return not isinstance(node, ast.FunctionDef) or node.name in functions


def project_definition(node: ast.stmt, functions: tuple[str, ...]) -> ast.stmt:
    if isinstance(node, ast.ClassDef):
        retained = (*functions, "__init__")
        node.body = [child for child in node.body if keep_definition(child, retained)] or [ast.Pass()]
    return node


def boundary(module: str, text: str) -> set[str]:
    return boundary_violations(module, text, module.rpartition(".")[0])


@pytest.mark.parametrize("operation", ["list_orders", "trace_order", "list_through_alias"])
def test_service_returns_domain_results_not_private_ports(operation: str) -> None:
    text = selected_source("coffee-services", "order_service.py", operation)
    assert boundary(SERVICE, text) == set()


@pytest.mark.parametrize("operation", [
    "return_storage", "yield_storage", "tuple_storage", "list_storage",
    "mapping_storage", "alias_storage", "annotated_storage", "unpack_storage",
    "assign_storage", "callback_storage", "keyword_storage", "copied_storage",
    "constructor_escape",
])
def test_service_ports_cannot_escape_through_values_or_aliases(operation: str) -> None:
    text = selected_source("coffee-services", "order_service.py", operation)
    assert "service leaks private dependency self._repository" in boundary(SERVICE, text)


@pytest.mark.parametrize("operation", ["public_attribute", "raw_session"])
def test_service_ports_are_private_and_have_no_database_handles(operation: str) -> None:
    text = selected_source("coffee-services", "order_service.py", operation)
    assert any("handle" in violation for violation in boundary(SERVICE, text))


@pytest.mark.parametrize("replacement", ["repository", "object", '"RepositoryProtocol"'])
def test_service_constructor_requires_the_domain_protocol(replacement: str) -> None:
    text = selected_source("coffee-services", "order_service.py", "list_orders")
    text = text.replace("repository: RepositoryProtocol", f"repository: {replacement}")
    found = boundary(SERVICE, text)
    assert bool(found) is (replacement != '"RepositoryProtocol"')
    if found:
        assert "service _repository must accept a domain protocol" in found


@pytest.mark.parametrize("module", ["atlas.cli.orders", "atlas.metrics.orders", "atlas.domain.orders"])
def test_nonservice_modules_cannot_accept_private_ports(module: str) -> None:
    text = selected_source("coffee-services", "order_service.py", "list_orders")
    assert "atlas.domain.repositories.RepositoryProtocol" in boundary(module, text)


@pytest.mark.parametrize("operation", ["repository_service", "navigation_service", "migrate_database"])
def test_factory_wraps_context_ports_in_services(operation: str) -> None:
    text = selected_source("coffee-storage", "factories.py", operation)
    assert boundary(FACTORY, text) == set()


@pytest.mark.parametrize("operation", ["expose_repository", "expose_nested_repository", "return_repository", "expose_reader"])
def test_factory_context_ports_cannot_escape(operation: str) -> None:
    text = selected_source("coffee-storage", "factories.py", operation)
    assert "service leaks private dependency self._repository" in boundary(FACTORY, text)


def test_factory_cannot_access_repository_session() -> None:
    text = selected_source("coffee-storage", "factories.py", "use_session")
    assert "database handle/operation repository.session" in boundary(FACTORY, text)


@pytest.mark.parametrize("replacement", [
    "repository_store", "RepositoryStore as _repository_store", "repository_session as _repository_store",
])
def test_factory_operation_imports_are_exact_and_private(replacement: str) -> None:
    text = selected_source("coffee-storage", "factories.py", "repository_service")
    text = text.replace("repository_store as _repository_store", replacement)
    assert any("factory" in violation for violation in boundary(FACTORY, text))


@pytest.mark.parametrize("operation", ["configure_connection", "begin_connection", "readonly_connection"])
def test_infrastructure_allows_only_literal_connection_setup(operation: str) -> None:
    text = selected_source("coffee-storage", "database.py", operation)
    assert boundary(DATABASE, text) == set()
    assert boundary(REPOSITORY, text)


@pytest.mark.parametrize("operation", [
    "setup_with_parameters", "dynamic_setup", "chained_setup", "read_orders",
    "mapped_orders", "query_orders", "load_order", "save_order", "initialize_schema",
])
def test_infrastructure_cannot_query_domain_data_or_loosen_setup(operation: str) -> None:
    text = selected_source("coffee-storage", "database.py", operation)
    assert any("infrastructure" in violation for violation in boundary(DATABASE, text))


def test_in_memory_graph_repository_is_not_a_storage_port() -> None:
    text = source("coffee-services", "order_analysis.py")
    assert boundary("atlas.metrics.orders", text) == set()


def test_exact_repository_owner_allows_mapped_queries() -> None:
    text = selected_source("coffee-storage", "database.py", "mapped_orders", "save_order", "load_order")
    assert boundary(REPOSITORY, text) == set()
    assert boundary("atlas.persistence.coffee_repository", text)


@pytest.mark.parametrize("operation", [
    "read_orders", "textual_orders", "formatted_orders", "prefixed_orders",
    "literal_orders", "driver_orders", "raw_operator",
])
def test_even_exact_orm_owners_cannot_use_raw_sql(operation: str) -> None:
    text = selected_source("coffee-storage", "database.py", operation)
    assert any("raw" in violation for violation in boundary(REPOSITORY, text))


@pytest.mark.parametrize("operation", ["upgrade", "downgrade", "graph_name_collation"])
def test_frozen_revision_allows_schema_and_exact_existing_collation(operation: str) -> None:
    text = selected_source("coffee-storage", "revision.py", operation)
    assert boundary(REVISION, text) == set()


@pytest.mark.parametrize("operation", ["other_name_collation", "seed_orders", "query_orders", "connection_orders", "mapped_orders"])
def test_revision_ownership_never_allows_data_queries(operation: str) -> None:
    text = selected_source("coffee-storage", "revision.py", operation)
    assert boundary(REVISION, text)


def test_collation_exception_is_confined_to_one_exact_revision_and_expression() -> None:
    text = selected_source("coffee-storage", "revision.py", "graph_name_collation")
    assert boundary("atlas.persistence.migrations.versions.0001_initial", text)
    assert boundary(REVISION, text.replace("name COLLATE NOCASE", "customer COLLATE NOCASE"))
    assert boundary("atlas.persistence.migrations.versions.9999_coffee", text)


@pytest.mark.parametrize("operation, expected", [
    ("dynamic_plugin", "importlib.import_module"), ("builtin_plugin", "__import__"),
    ("evaluate_discount", "eval"), ("execute_discount", "exec"),
    ("builtin_evaluate", "builtins.eval"), ("registry_plugin", "sys.modules"),
    ("reflective_storage", "getattr"), ("reflective_write", "setattr"),
    ("dictionary_storage", "dynamic reflection __dict__"),
    ("attribute_storage", "dynamic reflection __getattribute__"),
    ("dotted_storage", "reflective persistence handle extraction"),
    ("aliased_storage", "reflective persistence handle extraction"),
    ("method_storage", "reflective persistence handle extraction"),
])
def test_dynamic_and_reflective_access_cannot_hide_in_aliases(operation: str, expected: str) -> None:
    tree = ast.parse(source("coffee-services", "reflection.py"))
    aliases = import_aliases(tree, "atlas.services")
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == operation)
    found = set().union(*(node_dynamic_violations(node, aliases, "atlas.services") for node in ast.walk(function)))
    if operation == "dynamic_plugin":
        text = selected_source("coffee-services", "reflection.py", operation)
        found = dynamic_import_violations(text, "atlas.services")
    assert expected in found


@pytest.mark.parametrize("operation", ["public_customer", "public_label"])
def test_public_domain_introspection_is_not_private_port_extraction(operation: str) -> None:
    tree = ast.parse(source("coffee-services", "reflection.py"))
    aliases = import_aliases(tree, "atlas.services")
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == operation)
    assert not set().union(*(node_dynamic_violations(node, aliases, "atlas.services") for node in ast.walk(function)))


def test_exact_public_check_config_lookup_has_one_owner() -> None:
    text = source("check-config", "check_limits.py")
    assert boundary("atlas.metrics.check", text) == set()
    assert "getattr" in boundary("atlas.metrics.other", text)


@pytest.mark.parametrize("old, new", [
    ("getattr(config, rule)", 'getattr(config, "_repository")'),
    ('("maxParameters", "parameterCount", {"function", "method"})', '("_reader", "parameterCount", {"function", "method"})'),
    ("yield _MetricLimit(rule, metric, maximum)", "yield getattr(config, rule)"),
    ("from atlas.metrics.config import CheckConfig", "from atlas.metrics.config import CheckConfig\nfrom builtins import getattr"),
])
def test_public_config_exception_is_exact_not_general_reflection(old: str, new: str) -> None:
    text = source("check-config", "check_limits.py")
    assert old in text
    assert any("getattr" in violation for violation in boundary("atlas.metrics.check", text.replace(old, new)))


def test_entities_allow_declarative_schema_without_io() -> None:
    text = selected_source("coffee-storage", "models.py", "label")
    assert entity_violations(text) == set()


@pytest.mark.parametrize("operation", ["execute", "save_order", "load_order", "export_order", "print_order", "open_export"])
def test_entities_cannot_gain_database_or_filesystem_behavior(operation: str) -> None:
    text = selected_source("coffee-storage", "models.py", operation)
    assert entity_violations(text)


def test_import_scan_tracks_relative_local_type_and_chained_aliases() -> None:
    text = source("coffee-services", "import_orders.py")
    targets = import_targets(text, "atlas.services")
    expected = {
        "atlas.persistence.repositories", "atlas.persistence.database",
        "atlas.persistence.models.RepositoryEntity", "atlas.persistence.navigation.GraphReader",
        "atlas.persistence.repositories.repository_store",
        "atlas.persistence.database.create_engine", "atlas.persistence.repositories.RepositoryStore",
    }
    assert expected <= targets
    assert expected <= boundary(SERVICE, text)


def test_architecture_dependencies_include_local_and_package_imports_not_types() -> None:
    text = source("coffee-services", "dependencies.py")
    package = "atlas.metrics.adapters"
    modules = {f"{package}.{language}" for language in ("java", "kotlin", "go", "rust", "python")}
    modules.add("atlas.domain.models")
    assert module_dependencies(ast.parse(text), modules, package) == {
        f"{package}.{language}" for language in ("java", "kotlin", "go", "rust")
    }


def test_bootstrap_only_reexports_public_service_factories() -> None:
    text = selected_source("coffee-services", "bootstrap.py")
    assert boundary("atlas.bootstrap", text) == set()


@pytest.mark.parametrize("operation", ["open_coffee_project", "initialize_coffee_project"])
def test_bootstrap_cannot_gain_composition_or_other_behavior(operation: str) -> None:
    text = selected_source("coffee-services", "bootstrap.py", operation)
    assert any("bootstrap must only re-export" in violation for violation in boundary("atlas.bootstrap", text))


@pytest.mark.parametrize("target", [
    "sqlite3", "pathlib", "atlas.services.repositories", "atlas.persistence.database",
    "sqlalchemy.orm.Session", "sqlalchemy.create_engine", "builtins.open",
])
def test_entity_and_record_import_ownership_is_exact(target: str) -> None:
    text = selected_source("coffee-storage", "models.py", "label")
    module, name = target.rsplit(".", 1) if "." in target else (target, None)
    extra = f"from {module} import {name}" if name else f"import {module}"
    assert target in entity_violations(text + "\n" + extra)
    records = selected_source("coffee-storage", "records.py", "order_record")
    assert target in graph_record_violations(records + "\n" + extra)


def test_graph_records_only_transform_in_memory_values() -> None:
    text = selected_source("coffee-storage", "records.py", "order_record", "order_names")
    assert graph_record_violations(text) == set()


@pytest.mark.parametrize("operation", ["export_records", "read_records", "lookup_record"])
def test_graph_records_cannot_gain_io(operation: str) -> None:
    text = selected_source("coffee-storage", "records.py", operation)
    assert graph_record_violations(text)
