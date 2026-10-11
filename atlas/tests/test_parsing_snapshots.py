"""Complete parsing records and every original native metadata/wrapper variant."""

import pytest

from tests.parsing_snapshot_support import import_policy_value, manifest, parser_value, structure_result
from tests.source_snapshot_fixture import assert_case_snapshot


@pytest.mark.parametrize("case", manifest("parsing_sources.json"), ids=lambda case: case["snapshot_id"])
def test_parser_records(case):
    assert_case_snapshot("parsing", case["snapshot_id"], parser_value(case))


@pytest.mark.parametrize("case", manifest("parsing_structures.json"), ids=lambda case: case["snapshot_id"])
def test_structure_native_variants(case):
    assert_case_snapshot("parsing", case["snapshot_id"], structure_result(case))


@pytest.mark.parametrize("case", manifest("parsing_import_policies.json"), ids=lambda case: case["snapshot_id"])
def test_import_policy_records(case):
    assert_case_snapshot("parsing", case["snapshot_id"], import_policy_value(case))
