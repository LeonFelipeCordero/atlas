"""Inclusive navigation limits, persisted ordering, and graph validation."""

from copy import deepcopy
from pathlib import Path

import pytest

from atlas.domain.repositories import RepositoryError
from atlas.services.factories import navigation_service, repository_service
from tests.services.test_navigation import artifact, BREW, FILE


@pytest.mark.parametrize("count", [30, 31])
def test_diagnostic_and_root_limits(database: Path, tmp_path: Path, count: int) -> None:
    payload = artifact(tmp_path)
    root = payload["nodes"][0]
    payload["nodes"] = [{**root, "stableKey": f"root:{i:03}"} for i in reversed(range(count))]
    payload["edges"] = []
    payload["diagnostics"] = [
        {"severity": "warning", "path": "café.py", "language": "python", "message": str(i)}
        for i in range(count)
    ]
    with repository_service(database) as repositories:
        indexed = repositories.save_folder(tmp_path, payload)
    with navigation_service(indexed.repositoryId, path=database) as navigation:
        overview = navigation.overview()
    assert [node["stableKey"] for node in overview["roots"]] == [f"root:{i:03}" for i in range(30)]
    assert overview["truncated"] is (count > 30)
    assert [row["message"] for row in overview["diagnostics"]] == [str(i) for i in range(30)]
    assert overview["diagnosticsTruncated"] is (count > 30)


@pytest.mark.parametrize("count", [100, 101])
def test_decorator_limit_and_exact_child_page(database: Path, tmp_path: Path, count: int) -> None:
    payload = artifact(tmp_path)
    payload["nodes"][1]["properties"]["decorators"] = [f"decorator{i}" for i in range(count)]
    with repository_service(database) as repositories:
        indexed = repositories.save_folder(tmp_path, payload)
    with navigation_service(indexed.repositoryId, path=database) as navigation:
        node = navigation.show(BREW)["node"]
        children = navigation.children(FILE, limit=3, offset=0)
    assert node["decorators"] == [f"decorator{i}" for i in range(100)]
    assert node["decoratorsTruncated"] is (count > 100)
    assert len(children["nodes"]) == 3
    assert children["truncated"] is False
    assert children["nextOffset"] is None


@pytest.mark.parametrize("count", [100, 101])
def test_ancestor_limit(database: Path, tmp_path: Path, count: int) -> None:
    payload = artifact(tmp_path)
    template = payload["nodes"][0]
    payload["nodes"] = [
        {**template, "stableKey": f"node:{i}", "parentStableKey": f"node:{i-1}" if i else None}
        for i in range(count + 1)
    ]
    payload["edges"] = []
    with repository_service(database) as repositories:
        indexed = repositories.save_folder(tmp_path, payload)
    with navigation_service(indexed.repositoryId, path=database) as navigation:
        shown = navigation.show(f"node:{count}")
    assert [node["stableKey"] for node in shown["ancestors"]] == [f"node:{i}" for i in range(count-1, count-101, -1)]
    assert shown["truncated"] is (count > 100)


@pytest.mark.parametrize("state", ["cycle", "missing_parent", "nodes", "edges", "diagnostics", "mutationCandidates", "decorators"])
def test_invalid_graph_preserves_previous_revision(database: Path, tmp_path: Path, state: str) -> None:
    payload = artifact(tmp_path)
    with repository_service(database) as repositories:
        previous = repositories.save_folder(tmp_path, payload)
    broken = deepcopy(payload)
    if state == "cycle":
        broken["nodes"][0]["parentStableKey"] = BREW
    elif state == "missing_parent":
        broken["nodes"][1]["parentStableKey"] = "missing"
    elif state == "decorators":
        broken["nodes"][1]["properties"]["decorators"] = "not-an-array"
    else:
        broken[state] = {}
    expected = RepositoryError if state == "missing_parent" else ValueError
    with pytest.raises(expected):
        with repository_service(database) as repositories:
            repositories.save_folder(tmp_path, broken)
    with repository_service(database) as repositories:
        assert repositories.get_architecture(previous.repositoryId) == previous


def test_search_ranks_exact_matches_before_substrings(database: Path, tmp_path: Path) -> None:
    payload = artifact(tmp_path)
    template = payload["nodes"][0]
    payload["nodes"] = [
        {**template, "stableKey": key, "name": name, "qualifiedName": qualified, "path": path, "level": level}
        for key, name, qualified, path, level in [
            ("substring", "xneedle", "xneedle", "xneedle", "file"),
            ("qualified", "other", "needle", "a", "file"),
            ("name", "needle", "other", "b", "file"),
            ("path-symbol", "other", "other", "needle", "callable"),
            ("path-file", "other", "other", "needle", "file"),
            ("needle", "other", "other", "z", "file"),
        ]
    ]
    payload["edges"] = []
    with repository_service(database) as repositories:
        indexed = repositories.save_folder(tmp_path, payload)
    with navigation_service(indexed.repositoryId, path=database) as navigation:
        rows = navigation.find("needle", limit=6)
    assert [node["stableKey"] for node in rows["nodes"]] == ["needle", "path-file", "path-symbol", "name", "qualified", "substring"]
    assert rows["truncated"] is False
