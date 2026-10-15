"""Entities declare schema; graph record helpers only transform in-memory values."""

import ast

from tests.test_architecture import ROOT, module_package
from tests.test_database_boundaries import (
    belongs_to,
    dynamic_import_violations,
    import_aliases,
    import_targets,
    qualified_name,
)

IO_IMPORTS = {
    "os",
    "sys",
    "pathlib",
    "io",
    "socket",
    "subprocess",
    "http",
    "urllib",
    "requests",
    "sqlite3",
    "alembic",
    "tempfile",
    "shutil",
}
ORM_IO_NAMES = {
    "Session",
    "AsyncSession",
    "Engine",
    "AsyncEngine",
    "Connection",
    "create_engine",
    "create_async_engine",
    "sessionmaker",
    "async_sessionmaker",
    "scoped_session",
    "select",
    "insert",
    "update",
    "delete",
    "Query",
}
IO_METHODS = {
    "query",
    "execute",
    "exec_driver_sql",
    "scalar",
    "scalars",
    "commit",
    "rollback",
    "flush",
    "connect",
    "begin",
    "create_all",
    "drop_all",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "open",
    "mkdir",
    "unlink",
    "bulk_save_objects",
    "bulk_insert_mappings",
    "bulk_update_mappings",
}


def entity_violations(source: str, package: str = "atlas.persistence") -> set[str]:
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    violations = dynamic_import_violations(source, package)
    forbidden = (
        "atlas.persistence.database",
        "atlas.persistence.repositories",
        "atlas.services",
        "atlas.cli",
        "atlas.bootstrap",
        "atlas.domain.repositories",
    )
    violations.update(
        target
        for target in import_targets(source, package)
        if entity_target_forbidden(target, forbidden)
    )
    for node in ast.walk(tree):
        violations.update(entity_behavior_violations(node, aliases))
    return violations


def entity_target_forbidden(target: str, forbidden: tuple[str, ...]) -> bool:
    if target.split(".")[0] in IO_IMPORTS or any(
        belongs_to(target, name) for name in forbidden
    ):
        return True
    if belongs_to(target, "sqlalchemy") and target.rsplit(".", 1)[-1] in ORM_IO_NAMES:
        return True
    return target in {"builtins.open", "builtins.input", "builtins.print"}


def entity_behavior_violations(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in IO_METHODS
    ):
        return {f"entity method {node.name}"}
    if not isinstance(node, ast.Call):
        return set()
    name = qualified_name(node.func, aliases)
    method = (
        node.func.attr
        if isinstance(node.func, ast.Attribute)
        else name.rsplit(".", 1)[-1]
    )
    if method in IO_METHODS or name in {"open", "builtins.open", "input", "print"}:
        return {f"I/O call {method}"}
    return set()


def graph_record_violations(source: str) -> set[str]:
    """Optional graph_records.py is not another repository or ORM layer."""
    violations = entity_violations(source)
    for target in import_targets(source, "atlas.persistence"):
        if target and target.split(".")[0] not in {"typing", "__future__"} and target not in {"json", "json.dumps"}:
            violations.add(target)
    return violations


def test_production_entities_declare_schema_without_io() -> None:
    path = ROOT / "persistence" / "models.py"
    assert path.is_file(), "ORM entity declarations belong in persistence/models.py"
    violations = entity_violations(
        path.read_text(encoding="utf-8"), module_package(path)
    )
    assert not violations, (
        f"{path.relative_to(ROOT)} violates entity isolation: {sorted(violations)}"
    )


def test_optional_production_graph_records_are_pure() -> None:
    path = ROOT / "persistence" / "graph_records.py"
    if path.exists():
        violations = graph_record_violations(path.read_text(encoding="utf-8"))
        assert not violations, (
            f"{path.relative_to(ROOT)} is not pure: {sorted(violations)}"
        )
