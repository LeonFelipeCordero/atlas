"""Complete CLI transcripts and semantic results for migrated operational tests.

Only volatile storage identities, timestamps and temporary roots are normalized.
Original tests retain assertions for their identity/lifetime relationships.
"""

import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from tests.source_snapshot_fixture import assert_case_snapshot, snapshot_value

_RESULTS: ContextVar[list[dict[str, Any]] | None] = ContextVar("cli_case_results", default=None)


def snapshot_result(value: Any, label: str) -> Any:
    results = _RESULTS.get()
    if results is not None:
        results.append({"kind": label, "value": snapshot_value(value)})
    return value


def normalized_field(key: str, value: Any, root: Path) -> Any:
    if key in {"createdAt", "importedAt"} and isinstance(value, int):
        return "<epoch-ms>"
    return normalize_transcript(value, root)


def normalize_transcript(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: normalized_field(key, item, root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_transcript(item, root) for item in value]
    if not isinstance(value, str):
        return value
    value = value.replace(str(root), "<tmp>")
    value = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", value)
    value = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)?", "<timestamp>", value)
    value = re.sub(r'("(?:createdAt|importedAt)"\s*:\s*)\d+', r'\1"<timestamp>"', value)
    value = re.sub(r"\b[0-9a-f]{32}\b", "<revision>", value)
    if "[parameters:" in value:
        value = re.sub(r"\b\d{13}\b", "<epoch-ms>", value)
    return value


@pytest.fixture(autouse=True)
def case_snapshots(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Scope instrumentation to importing modules; record every invocation in order."""
    results: list[dict[str, Any]] = []
    token = _RESULTS.set(results)
    invoke = CliRunner.invoke

    def recorded(runner: CliRunner, *args: Any, **kwargs: Any):
        result = invoke(runner, *args, **kwargs)
        results.append({
            "kind": "cli", "exit_code": result.exit_code,
            "output": result.output, "stdout": result.stdout, "stderr": result.stderr,
        })
        return result

    monkeypatch.setattr(CliRunner, "invoke", recorded)
    yield
    _RESULTS.reset(token)
    if results:
        case_id = request.node.path.stem.removeprefix("test_") + "--" + request.node.name
        case_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", case_id).rstrip("-")
        # Path.resolve symlink-loop classification is platform-dependent. The
        # original structured-status assertion remains the filesystem contract.
        if case_id != "graph_navigation--test_source_symlink_loop_is_structured":
            assert_case_snapshot("cli", case_id, normalize_transcript(results, tmp_path))
