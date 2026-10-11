"""Reviewed Python-snippet outputs; production architecture scans stay separate."""

import ast
import json

import pytest

from tests.database_boundary_policy import (
    boundary_violations,
    dynamic_import_violations,
    import_targets,
)
from tests.source_snapshot_fixture import CASE_ROOT, assert_case_snapshot, case_text
from tests.test_architecture import module_dependencies
from tests.test_persistence_entity_boundaries import (
    entity_violations,
    graph_record_violations,
)

CASES = [
    case
    for catalog in sorted((CASE_ROOT / "policy" / "catalog").glob("*.json"))
    for case in json.loads(catalog.read_text(encoding="utf-8"))
]


def policy_result(case: dict) -> set[str]:
    source = case_text("policy", case["id"])
    if case["operation"] == "boundary":
        return boundary_violations(case["module"], source, case["package"])
    if case["operation"] == "imports":
        return import_targets(source, case["package"])
    if case["operation"] == "dynamic":
        return dynamic_import_violations(source, case["package"])
    if case["operation"] == "entity":
        return entity_violations(source, case["package"])
    if case["operation"] == "graph-record":
        return graph_record_violations(source)
    assert case["operation"] == "dependencies"
    return module_dependencies(ast.parse(source), set(case["modules"]), case["package"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_policy_case_snapshot(case: dict) -> None:
    found = policy_result(case)
    assert_case_snapshot("policy", case["id"], sorted(found))
    # An independently retained polarity check guards against blessing an empty
    # forbidden baseline (or violations for an allowed source).
    assert (not found) is case["allowed"]
