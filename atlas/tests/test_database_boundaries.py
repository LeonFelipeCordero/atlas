"""Guard CLI -> service factories -> private domain ports <- exact ORM owners."""

import ast

import pytest

from tests.database_boundary_policy import (
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


@pytest.mark.parametrize(
    "module, target, blocked",
    [
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
        (
            "atlas.services.factories",
            "atlas.persistence.database.repository_session",
            True,
        ),
        (
            "atlas.services.factories",
            "atlas.persistence.repositories.RepositoryStore",
            True,
        ),
        ("atlas.services.factories", "atlas.persistence.navigation.GraphReader", True),
        (
            "atlas.services.factories",
            "atlas.persistence.repositories.repository_store",
            False,
        ),
        (
            "atlas.services.factories",
            "atlas.persistence.navigation.navigation_reader",
            False,
        ),
        (
            "atlas.services.factories",
            "atlas.persistence.database.migrate_database",
            False,
        ),
        ("atlas.persistence.migrations.versions.9999_other", "alembic.op", True),
    ],
)
def test_database_boundary_policy(module: str, target: str, blocked: bool) -> None:
    assert bool(forbidden_imports(module, {target})) is blocked


def test_every_production_package_is_boundary_sensitive() -> None:
    assert all(
        boundary_sensitive(module)
        for module in (
            "atlas.parsing.adapters",
            "atlas.metrics.adapters.python",
            "atlas.persistence.repositories",
            "atlas.future.worker",
        )
    )


def test_repository_ownership_is_frozen_and_pure_records_are_not_orm() -> None:
    assert REPOSITORY_MODULES == INFRASTRUCTURE | ORM_MODULES | {
        "atlas.persistence.graph_records"
    }
    assert REVISIONS == {
        "atlas.persistence.migrations.versions." + name
        for name in (
            "0001_initial",
            "0002_graph_nodes",
            "0003_graph_relations",
            "0004_drop_graph_artifact",
            "0005_mutation_ledger",
        )
    }


def test_production_modules_respect_database_boundaries() -> None:
    failures = []
    for path in sorted(ROOT.rglob("*.py")):
        found = boundary_violations(
            module_name(path), path.read_text(encoding="utf-8"), module_package(path)
        )
        if found:
            failures.append(f"{path.relative_to(ROOT)}: {sorted(found)}")
    assert not failures, "\n".join(failures)


def test_policy_helpers_fit_architecture_limits() -> None:
    from tests.test_architecture import control_depth

    for path in (ROOT.parents[1] / "tests").glob("*database_boundar*.py"):
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 600, path
        assert_policy_function_limits(path, source, control_depth)


def assert_policy_function_limits(path, source, control_depth) -> None:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 100, (
                path,
                node.name,
            )
            assert control_depth(node) <= 3, (path, node.name)
