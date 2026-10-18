"""Check write timestamps before lossy cross-process timestamp normalization."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from common import differences


def milliseconds(value) -> float:
    if type(value) is int:
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.timestamp() * 1000
    raise ValueError(f"Invalid timestamp: {value!r}")


def in_window(value, result: dict, path: str) -> list[dict]:
    expected_type = str if path.endswith("/indexed_at") else int
    if type(value) is not expected_type:
        return [{"path": path, "error": f"timestamp must be {expected_type.__name__}", "actual": value}]
    try:
        stamp = milliseconds(value)
        if result["started_ms"] - 1 <= stamp <= result["finished_ms"] + 1:
            return []
    except (ValueError, TypeError, OverflowError):
        pass
    return [{"path": path, "error": "timestamp must be valid and within this subprocess's wall-clock interval", "actual": value}]


@dataclass
class WriteTimestamps:
    result: dict
    migration: bool
    path: str

    def compare(self, before: dict, after: dict) -> list[dict]:
        old, new = before.get("data", {}), after.get("data", {})
        diffs = self.table(old, new, "repositories") + self.table(old, new, "repository_graphs")
        return diffs + output_diffs(new, self.result, self.path + "/output")

    def table(self, old: dict, new: dict, table: str) -> list[dict]:
        key = "id" if table == "repositories" else "repository_id"
        previous = {row[key]: row for row in old.get(table, [])}
        diffs = []
        for row in new.get(table, []):
            pointer = f"{self.path}/{table}/{row[key]}"
            diffs.extend(self.row(previous.get(row[key], {}), row, pointer))
        return diffs

    def row(self, prior: dict, row: dict, path: str) -> list[dict]:
        fields = ("created_at",) if "created_at" in row else ("imported_at", "indexed_at")
        if self.preserve(prior, row):
            return differences({field: prior.get(field) for field in fields}, {field: row.get(field) for field in fields}, path)
        return [diff for field in fields for diff in in_window(row.get(field), self.result, f"{path}/{field}")]

    def preserve(self, prior: dict, row: dict) -> bool:
        if self.migration or ("created_at" in row and prior):
            return True
        return bool(prior) and self.result["exit_code"] != 0 and row.get("graph_revision") == prior.get("graph_revision")


def output_diffs(data: dict, result: dict, path: str) -> list[dict]:
    try:
        value = json.loads(result["stdout"].split("\n\n### source", 1)[0])
    except (ValueError, KeyError):
        return []
    stored = {"createdAt": [row["created_at"] for row in data.get("repositories", [])],
              "importedAt": [row.get("imported_at") for row in data.get("repository_graphs", [])],
              "indexedAt": [row.get("indexed_at") for row in data.get("repository_graphs", [])]}
    return output_fields(value, stored, path)


def output_fields(value, stored: dict, path: str) -> list[dict]:
    if isinstance(value, list):
        return [diff for index, item in enumerate(value) for diff in output_fields(item, stored, f"{path}/{index}")]
    if not isinstance(value, dict):
        return []
    diffs = []
    for key, item in value.items():
        pointer = f"{path}/{key}"
        diffs.extend(output_field((key, item), stored, pointer))
        diffs.extend(output_fields(item, stored, pointer))
    return diffs


def output_field(entry: tuple, stored: dict, path: str) -> list[dict]:
    key, item = entry
    if key in stored and item is not None and item not in stored[key]:
        return [{"path": path, "error": "output timestamp differs from stored timestamp", "actual": item}]
    return []
