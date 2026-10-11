"""The original function-level map stays auditable after case expansion."""

import json
from pathlib import Path

MANIFEST_ROOT = Path(__file__).parent / "migration"


def mapped_functions(value) -> set[str]:
    if isinstance(value, list):
        return set().union(*(mapped_functions(item) for item in value))
    if not isinstance(value, dict):
        return set()
    found = {key for key in value if key.startswith("test_") and ".py::test_" in key}
    for field in ("old_test", "original_function"):
        if field in value:
            found.add(value[field])
    if isinstance(value.get("module"), str) and isinstance(value.get("test"), str):
        found.add(f"{value['module']}.py::{value['test']}")
    return found | set().union(*(mapped_functions(item) for item in value.values()))


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
