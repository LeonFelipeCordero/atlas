"""Complete mutation extraction models from the shared source fixtures."""

import json
from pathlib import Path

import pytest

from atlas.parsing.mutation import extract_mutation_sites

FIXTURES = Path(__file__).parent / "fixtures" / "mutation"
SNAPSHOTS = Path(__file__).parent / "snapshots" / "mutation" / "extraction"
CASES = [
    ("conditions", "py", "python"),
    ("conditions", "js", "javascript"),
    ("conditions", "ts", "typescript"),
    ("conditions", "tsx", "tsx"),
    ("interpolations", "py", "python"),
    ("interpolations", "js", "javascript"),
    ("interpolations", "js", "typescript"),
    ("interpolations", "js", "tsx"),
    ("ownership", "py", "python"),
    ("ownership", "js", "javascript"),
    ("ownership", "ts", "typescript"),
    ("ownership", "ts", "tsx"),
]


@pytest.mark.parametrize("fixture,suffix,language", CASES)
def test_mutation_extraction_snapshot(fixture, suffix, language):
    path = f"{fixture}.{suffix}"
    source = (FIXTURES / path).read_bytes()
    actual = extract_mutation_sites(path, language, source).model_dump(mode="json")
    expected = json.loads((SNAPSHOTS / f"{fixture}.{language}.json").read_text())
    assert actual == expected
