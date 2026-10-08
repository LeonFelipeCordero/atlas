"""Static guards: CLI -> bootstrap/service -> domain repository <- persistence."""

import ast
from importlib.util import resolve_name

import pytest

from tests.test_architecture import ROOT, module_name, module_package


def import_targets(source: str, package: str) -> set[str]:
    """Include aliases, relative imports, local imports, and type-only imports."""
    targets: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        targets.update(node_import_targets(node, package))
    return targets


def node_import_targets(node: ast.AST, package: str) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    name = "." * node.level + (node.module or "")
    target = resolve_name(name, package) if node.level else name
    return {target} | {f"{target}.{alias.name}" for alias in node.names}


def belongs_to(name: str, package: str) -> bool:
    return name == package or name.startswith(package + ".")


def forbidden_prefixes(module: str) -> list[str]:
    forbidden = []
    if not belongs_to(module, "atlas.persistence"):
        forbidden.extend(("sqlalchemy", "sqlite3", "alembic"))
        if module != "atlas.bootstrap":
            forbidden.append("atlas.persistence")
    if not belongs_to(module, "atlas.cli"):
        forbidden.append("atlas.bootstrap")
    if belongs_to(module, "atlas.services") or belongs_to(module, "atlas.domain"):
        forbidden.append("atlas.cli")
    if belongs_to(module, "atlas.domain"):
        forbidden.append("atlas.services")
    return forbidden


def matches_forbidden_prefix(target: str, forbidden: list[str]) -> bool:
    return any(belongs_to(target, prefix) for prefix in forbidden)


def forbidden_imports(module: str, targets: set[str]) -> set[str]:
    forbidden = forbidden_prefixes(module)
    return {target for target in targets if matches_forbidden_prefix(target, forbidden)}


@pytest.mark.parametrize("source, expected", [
    ("import sqlalchemy as sa", {"sqlalchemy"}),
    ("from sqlalchemy.orm import Session as S", {"sqlalchemy.orm", "sqlalchemy.orm.Session"}),
    ("from ..persistence import database as db", {
        "atlas.persistence", "atlas.persistence.database",
    }),
    ("from .. import persistence as db", {"atlas", "atlas.persistence"}),
    ("from atlas import persistence", {"atlas", "atlas.persistence"}),
    ("def run():\n    import sqlite3", {"sqlite3"}),
    ("if TYPE_CHECKING:\n    from ..persistence.models import RepositoryRow", {
        "atlas.persistence.models", "atlas.persistence.models.RepositoryRow",
    }),
    ("from ..bootstrap import repository_service", {
        "atlas.bootstrap", "atlas.bootstrap.repository_service",
    }),
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
    ("atlas.bootstrap", "atlas.persistence.database", False),
    ("atlas.bootstrap", "sqlalchemy.orm", True),
    ("atlas.persistence.database", "atlas.bootstrap", True),
    ("atlas.persistence.database", "sqlalchemy.orm", False),
    ("atlas.persistence.migrations.env", "alembic", False),
    ("atlas.persistence.models", "atlas.domain.repositories", False),
    ("atlas.cli.commands", "sqlalchemy_helpers", False),
])
def test_database_boundary_policy(module: str, target: str, blocked: bool) -> None:
    assert bool(forbidden_imports(module, {target})) is blocked


def test_production_modules_respect_database_boundaries() -> None:
    for path in sorted(ROOT.rglob("*.py")):
        targets = import_targets(path.read_text(encoding="utf-8"), module_package(path))
        forbidden = forbidden_imports(module_name(path), targets)
        assert not forbidden, f"{path.relative_to(ROOT)} has forbidden imports: {sorted(forbidden)}"
