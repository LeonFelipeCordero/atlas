"""Lossless deterministic serialization for complete-project snapshots."""

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tree_sitter_language_pack import StructureKind


def snapshot_value(value: Any) -> Any:
    """Preserve record order and optional fields; sort only unordered sets/maps."""
    if isinstance(value, BaseModel):
        return snapshot_value(value.model_dump())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: snapshot_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    return snapshot_collection(value)


def snapshot_collection(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): snapshot_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [snapshot_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (snapshot_value(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    return snapshot_scalar(value)


def snapshot_scalar(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, StructureKind):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value
