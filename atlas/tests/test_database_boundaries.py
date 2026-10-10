"""Static guards: CLI -> bootstrap/service -> domain repository <- persistence."""

import ast
from importlib.util import resolve_name

import pytest

from tests.test_architecture import ROOT, module_name, module_package


def import_targets(source: str, package: str) -> set[str]:
    """Include aliases, relative imports, local imports, and type-only imports."""
    targets: set[str] = set()
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    imported_roots = {name.split(".")[0] for name in aliases.values()}
    for node in ast.walk(tree):
        targets.update(node_import_targets(node, package))
        if isinstance(node, ast.Attribute):
            name = qualified_name(node, aliases)
            if name.split(".")[0] in imported_roots:
                targets.add(name)
    return targets


def import_aliases(tree: ast.AST, package: str) -> dict[str, str]:
    """Resolve imported names without executing production code."""
    aliases = {}
    for node in ast.walk(tree):
        aliases.update(node_import_aliases(node, package))
    return aliases


def node_import_aliases(node: ast.AST, package: str) -> dict[str, str]:
    if isinstance(node, ast.Import):
        return {
            alias.asname or alias.name.split(".")[0]: alias.name if alias.asname else alias.name.split(".")[0]
            for alias in node.names
        }
    if isinstance(node, ast.ImportFrom):
        target = resolved_import_module(node, package)
        return {alias.asname or alias.name: f"{target}.{alias.name}" for alias in node.names}
    return {}


def resolved_import_module(node: ast.ImportFrom, package: str) -> str:
    name = "." * node.level + (node.module or "")
    return resolve_name(name, package) if node.level else name


def qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{qualified_name(node.value, aliases)}.{node.attr}"
    return ""


def boundary_sensitive(module: str) -> bool:
    return module == "atlas.bootstrap" or any(
        belongs_to(module, prefix)
        for prefix in ("atlas.cli", "atlas.services", "atlas.domain", "atlas.persistence")
    )


def dynamic_import_violations(source: str, package: str) -> set[str]:
    """Do not let dynamic loading bypass the statically enforced layers."""
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    violations = set()
    for node in ast.walk(tree):
        violations.update(node_dynamic_violations(node, aliases, package))
    return violations


def node_dynamic_violations(node: ast.AST, aliases: dict[str, str], package: str) -> set[str]:
    builtins = {"builtins.__import__", "builtins.eval", "builtins.exec"}
    violations = {
        target for target in node_import_targets(node, package)
        if target.split(".")[0] in {"importlib", "runpy", "pkgutil"} or target in builtins
    }
    name = qualified_name(node, aliases)
    if name in builtins | {"__import__", "eval", "exec"}:
        violations.add(name)
    if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
        violations.add("wildcard import")
    return violations


def node_import_targets(node: ast.AST, package: str) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    target = resolved_import_module(node, package)
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
    if belongs_to(module, "atlas.persistence"):
        forbidden.extend(("atlas.cli", "atlas.services"))
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
    ("atlas.persistence.migrations.env", "atlas.persistence.models", False),
    ("atlas.persistence.repositories", "sqlalchemy.orm.Session", False),
    ("atlas.persistence.models", "atlas.domain.repositories", False),
    ("atlas.persistence.repositories", "atlas.services.repositories", True),
    ("atlas.persistence.models", "atlas.cli.commands", True),
    ("atlas.persistence.database", "atlas.domain.repositories", False),
    ("atlas.cli.commands", "sqlalchemy_helpers", False),
])
def test_database_boundary_policy(module: str, target: str, blocked: bool) -> None:
    assert bool(forbidden_imports(module, {target})) is blocked


@pytest.mark.parametrize("source", [
    "import atlas as app\napp.persistence.repositories.RepositoryStore",
    "def run():\n    from ..persistence import repositories as stores",
    "from typing import TYPE_CHECKING as TC\nif TC:\n    import atlas.persistence.models as entities",
    "import atlas.persistence as storage",
])
def test_package_aliases_and_nested_imports_cannot_hide_storage(source: str) -> None:
    assert forbidden_imports("atlas.services.repositories", import_targets(source, "atlas.services"))


@pytest.mark.parametrize("source", [
    "import importlib as loader\nloader.import_module('atlas.persistence')",
    "from importlib import import_module as load",
    "def run():\n    __import__('atlas.persistence')",
    "import builtins as b\nload = b.__import__",
    "from builtins import __import__ as load",
    "if TYPE_CHECKING:\n    import runpy",
    "exec('import atlas.persistence')",
    "from atlas import *",
])
def test_dynamic_loading_is_detected(source: str) -> None:
    assert dynamic_import_violations(source, "atlas.services")


@pytest.mark.parametrize("source", [
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from atlas.domain.repositories import RepositoryPort",
    "from sqlalchemy.orm import Session\nfrom atlas.persistence.models import RepositoryRow",
    "from alembic import op\nop.execute('SELECT importlib FROM legacy')",
])
def test_regular_imports_and_sql_strings_are_not_dynamic_loading(source: str) -> None:
    assert not dynamic_import_violations(source, "atlas.persistence")


def test_parser_dynamic_loading_is_outside_sensitive_layers() -> None:
    assert not boundary_sensitive("atlas.parsing.adapters")
    assert not boundary_sensitive("atlas.metrics.adapters.python")
    assert boundary_sensitive("atlas.persistence.repositories")


def test_production_modules_respect_database_boundaries() -> None:
    for path in sorted(ROOT.rglob("*.py")):
        targets = import_targets(path.read_text(encoding="utf-8"), module_package(path))
        forbidden = forbidden_imports(module_name(path), targets)
        assert not forbidden, f"{path.relative_to(ROOT)} has forbidden imports: {sorted(forbidden)}"
        if boundary_sensitive(module_name(path)):
            dynamic = dynamic_import_violations(path.read_text(encoding="utf-8"), module_package(path))
            assert not dynamic, f"{path.relative_to(ROOT)} uses dynamic imports: {sorted(dynamic)}"
