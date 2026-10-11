"""Pure AST import, alias and exact public-config reflection helpers."""

import ast
from importlib.util import resolve_name
from itertools import chain

from tests.source_snapshot_fixture import case_text


def belongs_to(name: str, package: str) -> bool:
    return name == package or name.startswith(package + ".")


def resolved_import_module(node: ast.ImportFrom, package: str) -> str:
    name = "." * node.level + (node.module or "")
    return resolve_name(name, package) if node.level else name


def node_import_targets(node: ast.AST, package: str) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    target = resolved_import_module(node, package)
    return {target} | {f"{target}.{alias.name}" for alias in node.names}


def node_import_aliases(node: ast.AST, package: str) -> dict[str, str]:
    if isinstance(node, ast.Import):
        return {alias.asname or alias.name.split(".")[0]: alias.name if alias.asname else alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        target = resolved_import_module(node, package)
        return {alias.asname or alias.name: f"{target}.{alias.name}" for alias in node.names}
    return {}


def qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        name = f"{qualified_name(node.value, aliases)}.{node.attr}"
        return aliases.get(name, name)
    if isinstance(node, ast.Call) and qualified_name(node.func, aliases) in {"getattr", "builtins.getattr"}:
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
            return f"{qualified_name(node.args[0], aliases)}.{node.args[1].value}"
    return ""


def assignment_pairs(node: ast.AST) -> list[tuple[ast.AST, ast.AST]]:
    if isinstance(node, ast.Assign):
        return [(target, node.value) for target in node.targets]
    if isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
        return [(node.target, node.value)]
    return []


def import_aliases(tree: ast.AST, package: str) -> dict[str, str]:
    """Track chained aliases too, so assigning an import does not launder it."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        aliases.update(node_import_aliases(node, package))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            aliases.setdefault(node.name, f"{package}.__local__.{node.name}")
    pairs = list(chain.from_iterable(map(assignment_pairs, ast.walk(tree))))
    return propagate_aliases(aliases, pairs, import_assignment_aliases)


def import_assignment_aliases(target, value, aliases):
    name = qualified_name(value, aliases)
    if isinstance(target, ast.Name) and name and target.id not in aliases:
        return {target.id: name}
    return {}


def apply_alias_pairs(aliases, pairs, assignment):
    for target, value in pairs:
        aliases.update(assignment(target, value, aliases))


def propagate_aliases(aliases, pairs, assignment):
    for _ in range(len(pairs) + 1):
        previous = dict(aliases)
        apply_alias_pairs(aliases, pairs, assignment)
        if previous == aliases:
            break
    return aliases


def import_targets(source: str, package: str) -> set[str]:
    """Include aliases, relative/local/TYPE_CHECKING imports and qualified access."""
    tree = ast.parse(source)
    aliases = import_aliases(tree, package)
    imported_roots = {name.split(".")[0] for node in ast.walk(tree) for name in node_import_aliases(node, package).values()}
    targets: set[str] = set()
    for node in ast.walk(tree):
        targets.update(node_import_targets(node, package))
        name = qualified_name(node, aliases)
        if isinstance(node, (ast.Attribute, ast.Call)) and name.split(".")[0] in imported_roots:
            targets.add(name)
    return targets


CHECK_LIMIT_LOOKUP = case_text("policy", "check-limit-lookup-template")


def main_config_reflection_ids(tree: ast.AST, aliases: dict[str, str]) -> set[int]:
    """Only main's exact public CheckConfig rule enumeration permits reflection."""
    if not public_config_aliases(aliases):
        return set()
    candidates = [node for node in ast.walk(tree) if check_lookup_definition(node)]
    if not exact_lookup_definitions(candidates):
        return set()
    return {id(node) for node in ast.walk(candidates[-1]) if check_lookup_getattr(node)}


def exact_lookup_definitions(candidates: list[ast.AST]) -> bool:
    expected = ast.parse(CHECK_LIMIT_LOOKUP).body
    return [ast.dump(node) for node in candidates] == [ast.dump(node) for node in expected]


def public_config_aliases(aliases: dict[str, str]) -> bool:
    return aliases.get("CheckConfig") == "atlas.metrics.config.CheckConfig" and aliases.get("getattr", "getattr") == "getattr"


def check_lookup_definition(node: ast.AST) -> bool:
    if isinstance(node, ast.FunctionDef):
        return node.name == "_enabled_limits"
    return isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {"RULES", "DEPENDENCY_RULES"} for target in node.targets)


def check_lookup_getattr(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "getattr" or isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
