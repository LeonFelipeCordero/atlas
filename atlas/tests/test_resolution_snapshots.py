"""Complete parsed and resolved records, reviewed against independent regressions."""

import pytest

from tests.resolution_snapshot_support import MANIFEST, case_records
from tests.source_snapshot_fixture import assert_case_snapshot


@pytest.mark.parametrize("case_id", sorted(MANIFEST["cases"]))
def test_resolution_case_snapshot(case_id: str) -> None:
    assert_case_snapshot("resolution", case_id, case_records(case_id))
