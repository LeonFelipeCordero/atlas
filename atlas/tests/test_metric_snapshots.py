"""Callable enrichment, grammar complexity and finding threshold baselines."""

import pytest

from tests.metric_snapshot_support import complexity_value, metric_value
from tests.parsing_snapshot_support import manifest
from tests.source_snapshot_fixture import assert_case_snapshot


@pytest.mark.parametrize("case", manifest("metric_sources.json"), ids=lambda case: case["snapshot_id"])
def test_callable_records(case):
    assert_case_snapshot("metrics", case["snapshot_id"], metric_value(case))


@pytest.mark.parametrize("case", manifest("metric_complexity.json"), ids=lambda case: case["snapshot_id"])
def test_grammar_complexity(case):
    assert_case_snapshot("metrics", case["snapshot_id"], complexity_value(case))
