"""Shared source corpus access and lossless deterministic snapshot serialization."""

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tree_sitter_language_pack import StructureKind

CASE_ROOT = Path(__file__).parent / "fixtures" / "cases"
SNAPSHOT_ROOT = Path(__file__).parent / "snapshots" / "cases"


def case_bytes(family: str, case_id: str, path: str = "sample.py") -> bytes:
    return (CASE_ROOT / family / case_id / path).read_bytes()


def case_text(family: str, case_id: str, path: str = "sample.py") -> str:
    return case_bytes(family, case_id, path).decode("utf-8")


def case_sources(family: str, case_id: str) -> dict[str, str]:
    root = CASE_ROOT / family / case_id
    return {
        path.relative_to(root).as_posix(): path.read_bytes().decode("utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def snapshot_value(value: Any) -> Any:
    """Preserve record order and optional fields; sort only unordered sets/maps."""
    if isinstance(value, BaseModel):
        return snapshot_value(value.model_dump())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: snapshot_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(key): snapshot_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [snapshot_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (snapshot_value(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, StructureKind):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def assert_case_snapshot(family: str, case_id: str, value: Any) -> None:
    expected = json.loads(
        (SNAPSHOT_ROOT / family / f"{case_id}.json").read_text(encoding="utf-8")
    )
    assert snapshot_value(value) == expected, f"{family}/{case_id}"
