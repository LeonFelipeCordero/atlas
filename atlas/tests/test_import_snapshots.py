"""Complete deterministic import graphs, extraction facts, metrics and diagnostics."""

import json
from pathlib import Path

import pytest

from tests.import_snapshot_support import import_snapshot
from tests.source_snapshot_fixture import assert_case_snapshot

CASES = json.loads((Path(__file__).parent / "migration/import_cases.json").read_text())


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_import_case_snapshot(tmp_path: Path, case_id: str) -> None:
    spec = CASES[case_id]
    value = import_snapshot(tmp_path, case_id, spec["seam"], spec["language"])
    assert_case_snapshot("imports", case_id, value)
