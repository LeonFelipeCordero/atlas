"""The original function-level map stays auditable after case expansion."""

import json
from pathlib import Path

MANIFEST_ROOT = Path(__file__).parent / "migration"


def mapped_functions(value) -> set[str]:
    if isinstance(value, list):
        return set().union(*(mapped_functions(item) for item in value))
    if not isinstance(value, dict):
        return set()
    return mapped_record_functions(value) | set().union(
        *(mapped_functions(item) for item in value.values())
    )


def mapped_record_functions(value: dict) -> set[str]:
    found = {key for key in value if key.startswith("test_") and ".py::test_" in key}
    for field in ("old_test", "original_function"):
        if field in value:
            found.add(value[field])
    if isinstance(value.get("module"), str) and isinstance(value.get("test"), str):
        found.add(f"{value['module']}.py::{value['test']}")
    return found


PATH_FIELDS = {"snapshot", "snapshots", "fixture", "fixture_paths", "fixture_trees", "fixture_tree", "destination"}


def record_paths(value: dict) -> set[str]:
    return set().union(*(path_values(item) for key, item in value.items() if key in PATH_FIELDS))


def path_values(value) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def manifest_paths(value) -> set[str]:
    if isinstance(value, list):
        return set().union(*(manifest_paths(item) for item in value))
    if isinstance(value, dict):
        return record_paths(value) | set().union(*(manifest_paths(item) for item in value.values()))
    return set()


def destination_path(path: str) -> Path | None:
    if "<" in path or "*" in path:
        return None
    if path.startswith("atlas/tests/"):
        return MANIFEST_ROOT.parents[2] / path
    if path.startswith("tests/"):
        return MANIFEST_ROOT.parents[1] / path
    if path.startswith(("fixtures/", "snapshots/")):
        return MANIFEST_ROOT.parent / path
    return None


def test_concrete_migration_destinations_exist() -> None:
    paths = set().union(*(manifest_paths(json.loads(path.read_text())) for path in MANIFEST_ROOT.glob("*.json")))
    destinations = [destination_path(path) for path in paths]
    assert not [path for path in destinations if path is not None and not path.exists()]


def test_all_inventory_functions_have_migration_destinations() -> None:
    inventory = set(
        (MANIFEST_ROOT / "inventory.txt").read_text(encoding="utf-8").splitlines()
    )
    mapped = set().union(
        *(
            mapped_functions(json.loads(path.read_text(encoding="utf-8")))
            for path in MANIFEST_ROOT.glob("*.json")
        )
    )
    assert not inventory - mapped, sorted(inventory - mapped)
