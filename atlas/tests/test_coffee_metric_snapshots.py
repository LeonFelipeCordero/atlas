"""Complete quantitative CLI records supplement coffee Markdown/graph snapshots."""

import json

import pytest
from click.testing import CliRunner

from atlas.cli import main
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES
from tests.source_snapshot_fixture import assert_case_snapshot


def coffee_metric_output(language):
    result = CliRunner().invoke(
        main, ["report", "--folder", str(FIXTURE_ROOT / language), "--format", "json"]
    )
    assert result.exception is None, result.output
    return {"exit_code": result.exit_code, "output": json.loads(result.output)}


@pytest.mark.parametrize("language", LANGUAGES)
def test_coffee_quantitative_snapshot(language):
    assert_case_snapshot("coffee-metrics", language, coffee_metric_output(language))
