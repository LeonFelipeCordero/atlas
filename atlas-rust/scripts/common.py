"""Strict comparison and isolated subprocess execution."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "atlas/tests/code_samples"
SNAPSHOTS = REPO / "atlas/tests/snapshots"
LANGUAGES = ("java", "kotlin", "go", "rust", "javascript", "typescript", "elixir", "python", "tsx")
TIMESTAMPS = {"indexedAt", "createdAt", "importedAt", "indexed_at", "created_at", "imported_at"}
ROOT_PATHS = {"root", "rootPath", "root_path", "absolutePath", "location"}


def normalized_item(key: str, item: Any, root: Path) -> Any:
    if key in TIMESTAMPS and item is not None:
        return f"<timestamp:{type(item).__name__}>"
    if key in ROOT_PATHS:
        return normalized_root(item, root)
    return normalize(item, root)


def normalize(value: Any, root: Path) -> Any:
    """Never drop fields, sort arrays, round numbers, or rewrite identities."""
    if isinstance(value, dict):
        return {key: normalized_item(key, item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item, root) for item in value]
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode()}
    return value


def normalized_root(value: Any, root: Path) -> Any:
    if isinstance(value, str) and (value == str(root) or value.startswith(str(root) + "/")):
        return "/samples/coffee/" + root.name + value[len(str(root)):]
    return value


def differences(expected: Any, actual: Any, path: str = "") -> list[dict]:
    if type(expected) is not type(actual):
        return [{"path": path, "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        return object_differences((expected, actual), path)
    if isinstance(expected, list):
        return array_differences((expected, actual), path)
    return [] if expected == actual else [{"path": path, "expected": expected, "actual": actual}]


def object_differences(values: tuple, path: str) -> list[dict]:
    expected, actual = values
    missing = [{"path": path + "/" + key, "missing": "actual"} for key in expected.keys() - actual.keys()]
    extra = [{"path": path + "/" + key, "missing": "expected"} for key in actual.keys() - expected.keys()]
    nested = []
    for key in expected.keys() & actual.keys():
        pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
        nested.extend(differences(expected[key], actual[key], pointer))
    return sorted(missing + extra + nested, key=lambda diff: diff["path"])


def array_differences(values: tuple, path: str) -> list[dict]:
    expected, actual = values
    result = [] if len(expected) == len(actual) else [{"path": path, "expectedLength": len(expected), "actualLength": len(actual)}]
    for index, (left, right) in enumerate(zip(expected, actual)):
        result.extend(differences(left, right, f"{path}/{index}"))
    return result


def output_value(text: str, root: Path) -> Any:
    try:
        return normalize(json.loads(text), root)
    except ValueError:
        return source_text(text, root)


def source_text(text: str, root: Path) -> str:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("{"):
        try:
            header = json.dumps(normalize(json.loads(lines[0]), root), ensure_ascii=False, sort_keys=True)
            return header + "\n" + "".join(lines[1:])
        except ValueError:
            pass
    return text


@dataclass
class Process:
    command: list[str]
    cwd: Path
    database: Path
    timeout: float
    extra_env: dict = field(default_factory=dict)

    def environment(self) -> dict:
        return {**os.environ, "DATABASE_PATH": str(self.database), "XDG_DATA_HOME": str(self.database.parent / "xdg"),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8",
                "ATLAS_PARITY_UUID": "", **self.extra_env}

    def run(self) -> dict:
        start = time.perf_counter_ns()
        try:
            result = subprocess.run(self.command, cwd=self.cwd, env=self.environment(), capture_output=True,
                                    timeout=self.timeout, check=False)
            output = self.output(result.stdout, result.stderr)
            output.update(exit_code=result.returncode, timeout=False)
        except subprocess.TimeoutExpired as error:
            output = self.output(error.stdout or b"", error.stderr or b"")
            output.update(exit_code=None, timeout=True)
        return {**output, "command": self.command, "elapsed_ns": time.perf_counter_ns() - start}

    def output(self, stdout: bytes, stderr: bytes) -> dict:
        return {"stdout": stdout.decode("utf-8", "replace"), "stderr": stderr.decode("utf-8", "replace")}


def result_value(result: dict, root: Path) -> dict:
    return {"exit_code": result["exit_code"], "stdout": output_value(result["stdout"], root),
            "stderr": output_value(result["stderr"], root), "timeout": result["timeout"]}


def require(result: dict, label: str) -> None:
    if result["exit_code"] != 0 or result["timeout"]:
        raise RuntimeError(f"{label}: {result['exit_code']}\n{result['stdout']}\n{result['stderr']}")
