"""Navigation integration tests using the shared, migrated SQLite database fixture."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from atlas.domain.navigation import NavigationError, PathRequest, TraversalRequest
from atlas.domain.repositories import GraphDTO
from atlas.services.factories import navigation_service, repository_service


FILE = "file:café.py"
BREW = "function:brew"
GRIND = "function:grind"
SERVE = "function:serve"
EXTERNAL = "external:milk"
ISOLATED = "function:isolated"


def artifact(root: Path) -> dict[str, Any]:
    file: dict[str, Any] = {
        "stableKey": FILE, "type": "file", "kind": "file", "level": "file",
        "language": "python", "name": "café.py", "qualifiedName": "café.py",
        "path": "café.py", "parentStableKey": None, "depth": 0,
        "ancestorStableKeys": [], "properties": {"lineCount": 5},
    }
    brew: dict[str, Any] = {
        **file, "stableKey": BREW, "type": "function", "kind": "function", "level": "callable",
        "name": "brew", "qualifiedName": "café.brew", "parentStableKey": FILE,
        "startLine": 2, "depth": 1, "ancestorStableKeys": [FILE],
        "properties": {"lineCount": 3, "cyclomaticComplexity": 8},
    }
    result: dict[str, Any] = {
        "schemaVersion": 2, "nodes": [file, brew],
        "repository": {"path": str(root), "name": root.name, "indexedAt": "2026-01-02T03:04:05Z"},
    }
    source = b"# menu\r\ndef brew():\r\n    grind()\r\n    return 'coffee'\r\n# end\r\n"
    (root / "café.py").write_bytes(source)
    file["properties"].update(bytes=len(source), sha256=hashlib.sha256(source).hexdigest())
    brew.update(endLine=4, signature="brew()")
    brew["properties"].update(decorators=["cached"], visibility="public")
    for key, name, parent in [
        (GRIND, "grind", BREW), (SERVE, "serve_%", FILE), (ISOLATED, "isolated", FILE),
    ]:
        result["nodes"].append({
            **brew, "stableKey": key, "name": name, "qualifiedName": f"café.{name}",
            "parentStableKey": parent, "properties": {},
            "depth": 2 if parent == BREW else 1,
            "ancestorStableKeys": [FILE, BREW] if parent == BREW else [FILE],
        })
    result["nodes"].append({
        **brew, "stableKey": EXTERNAL, "name": "milk", "qualifiedName": "milk",
        "type": "external", "kind": "external", "level": "external", "path": None,
        "parentStableKey": None, "depth": 0, "ancestorStableKeys": [], "properties": {},
    })
    result["edges"] = [
        {"sourceStableKey": source, "targetStableKey": target, "type": relation,
         "confidence": "EXTRACTED", "path": "café.py", "line": 3, "evidence": "call"}
        for source, target, relation in [
            (BREW, GRIND, "CALLS"), (GRIND, SERVE, "CALLS"), (SERVE, BREW, "CALLS"),
            (BREW, EXTERNAL, "REFERENCES"),
        ]
    ]
    result["diagnostics"] = [
        {"severity": "error", "path": "café.py", "language": "python", "message": "local diagnostic"},
        {"severity": "error", "path": "other.py", "language": "python", "message": "unrelated diagnostic"},
    ]
    return result


@pytest.fixture
def indexed(database: Path, tmp_path: Path) -> GraphDTO:
    with repository_service(database) as repositories:
        return repositories.save_folder(tmp_path, artifact(tmp_path))


def keys(nodes: list[dict[str, Any]]) -> list[str]:
    return [node["stableKey"] for node in nodes]


def test_overview_and_show_persisted_details(database: Path, indexed: GraphDTO) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        overview = navigation.overview()
        shown = navigation.show(BREW)
        nested = navigation.show(GRIND)
        root = navigation.show(FILE)
    assert overview["repositoryId"] == indexed.repositoryId
    assert overview["graphRevision"] == indexed.graphRevision
    assert overview["indexedAt"] == "2026-01-02T03:04:05Z"
    assert overview["levels"] == [
        {"level": "callable", "count": 4}, {"level": "external", "count": 1},
        {"level": "file", "count": 1},
    ]
    assert overview["relations"] == [{"type": "CALLS", "count": 3}, {"type": "REFERENCES", "count": 1}]
    assert set(keys(overview["roots"])) == {FILE, EXTERNAL}
    assert overview["truncated"] is False
    assert keys(shown["ancestors"]) == [FILE]
    assert keys(nested["ancestors"]) == [BREW, FILE]
    assert root["ancestors"] == []
    assert shown["truncated"] is False
    assert shown["node"]["signature"] == "brew()"
    assert shown["node"]["metrics"]["cyclomaticComplexity"] == 8
    assert shown["node"]["decorators"] == ["cached"]
    assert shown["node"]["decoratorsTruncated"] is False
    assert shown["node"]["visibility"] == "public"
    assert shown["node"]["external"] is False
    assert root["node"]["file"]["bytes"] == len((Path(indexed.rootPath or "") / "café.py").read_bytes())
    assert [row["message"] for row in shown["diagnostics"]] == ["local diagnostic"]
    assert shown["diagnosticsTruncated"] is False


def test_children_pagination_preserves_import_order(database: Path, indexed: GraphDTO) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        first = navigation.children(FILE, limit=2, offset=0)
        second = navigation.children(FILE, limit=2, offset=first["nextOffset"])
        past_end = navigation.children(FILE, limit=2, offset=10)
        leaf = navigation.children(GRIND, limit=2, offset=0)
    assert keys(first["nodes"]) == [BREW, SERVE]
    assert first["truncated"] is True
    assert first["nextOffset"] == 2
    assert keys(second["nodes"]) == [ISOLATED]
    assert second["truncated"] is False
    assert second["nextOffset"] is None
    for page in [past_end, leaf]:
        assert page["nodes"] == []
        assert page["truncated"] is False
        assert page["nextOffset"] is None


@pytest.mark.parametrize("scenario", [
    ("BREW", [BREW]), ("CAFé.PY", [FILE, BREW, GRIND, ISOLATED, SERVE]),
    ("%", [SERVE]), ("_", [SERVE]), ("serve_%", [SERVE]),
    ("function:brew", [BREW]), ("FUNCTION:BREW", []), ("' OR 1=1 --", []),
])
def test_find_literal_and_case_handling(
    database: Path, indexed: GraphDTO, scenario: tuple[str, list[str]],
) -> None:
    query, expected = scenario
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.find(query, limit=20)
    assert keys(result["nodes"]) == expected
    assert result["truncated"] is False
    assert result["filters"] == {"query": query, "limit": 20}


def test_find_limit_reports_more_results(database: Path, indexed: GraphDTO) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        limited = navigation.find("café.py", limit=1)
        complete = navigation.find("café.py", limit=5)
    assert keys(limited["nodes"]) == [FILE]
    assert limited["truncated"] is True
    assert len(complete["nodes"]) == 5
    assert complete["truncated"] is False


@pytest.mark.parametrize("scenario", [
    ("out", [BREW, GRIND], [0]), ("in", [BREW, SERVE], [2]),
    ("both", [BREW, GRIND, SERVE], [0, 2]),
])
def test_context_directions_and_relation_filter(
    database: Path, indexed: GraphDTO, scenario: tuple[Any, ...],
) -> None:
    direction, expected_nodes, expected_edges = scenario
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.context(TraversalRequest(BREW, direction, ["CALLS"], 1, 20, 20))
    assert keys(result["nodes"]) == expected_nodes
    assert [edge["ordinal"] for edge in result["edges"]] == expected_edges
    assert result["boundaries"] == [
        {"stableKey": key, "reason": "depth", "expandable": True} for key in expected_nodes[1:]
    ]
    assert result["truncated"] is True


def test_context_cycles_and_external_boundaries(database: Path, indexed: GraphDTO) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.context(TraversalRequest(BREW, "both", ["CALLS", "REFERENCES"], 10, 20, 20))
    assert set(keys(result["nodes"])) == {BREW, GRIND, SERVE, EXTERNAL}
    assert sorted(edge["ordinal"] for edge in result["edges"]) == [0, 1, 2, 3]
    assert result["boundaries"] == [
        {"stableKey": EXTERNAL, "reason": "external_unresolved_or_ambiguous", "expandable": False},
    ]
    assert result["truncated"] is False
    assert next(node for node in result["nodes"] if node["stableKey"] == EXTERNAL)["external"] is True


@pytest.mark.parametrize("scenario", [
    (0, 20, 20, "depth", [BREW], []),
    (10, 1, 20, "maxNodes", [BREW], []),
    (10, 20, 0, "maxEdges", [BREW], []),
    (10, 20, 1, "maxEdges", [BREW, GRIND], [0]),
])
def test_context_budgets(
    database: Path, indexed: GraphDTO, scenario: tuple[Any, ...],
) -> None:
    depth, max_nodes, max_edges, reason, expected_nodes, ordinals = scenario
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.context(TraversalRequest(BREW, "out", ["CALLS"], depth, max_nodes, max_edges))
    assert keys(result["nodes"]) == expected_nodes
    assert [edge["ordinal"] for edge in result["edges"]] == ordinals
    assert result["truncated"] is True
    assert reason in {boundary["reason"] for boundary in result["boundaries"]}
    assert len(result["nodes"]) <= max_nodes
    assert len(result["edges"]) <= max_edges


@pytest.mark.parametrize("scenario", [
    (SERVE, "out", 10, "found", [BREW, GRIND, SERVE], [0, 1]),
    (SERVE, "in", 10, "found", [BREW, SERVE], [2]),
    (BREW, "out", 0, "found", [BREW], []),
    (SERVE, "out", 1, "unknown", [], []),
    (ISOLATED, "out", 10, "not_found", [], []),
])
def test_path_status_and_edge_order(
    database: Path, indexed: GraphDTO, scenario: tuple[Any, ...],
) -> None:
    target, direction, depth, status, path, ordinals = scenario
    request = PathRequest(target, TraversalRequest(BREW, direction, ["CALLS"], depth, 20, 20))
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.path(request)
    assert result["status"] == status
    assert result["path"] == path
    assert [edge["ordinal"] for edge in result["pathEdges"]] == ordinals


def test_source_verified_spans_and_pagination(database: Path, indexed: GraphDTO) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        first = navigation.source(BREW, max_lines=2, start_line=None)["source"]
        last = navigation.source(BREW, max_lines=2, start_line=first["nextStartLine"])["source"]
        batch = navigation.sources([FILE, BREW, EXTERNAL], max_lines=1, start_line=1)["sources"]
    assert first == {
        "status": "ok", "path": "café.py", "startLine": 2, "endLine": 3,
        "lines": ["def brew():", "    grind()"], "truncated": True, "nextStartLine": 4,
    }
    assert last == {
        "status": "ok", "path": "café.py", "startLine": 4, "endLine": 4,
        "lines": ["    return 'coffee'"], "truncated": False, "nextStartLine": None,
    }
    assert keys(batch) == [FILE, BREW, EXTERNAL]
    assert batch[0]["lines"] == ["# menu"]
    assert batch[1]["lines"] == ["def brew():"]
    assert batch[2] == {"stableKey": EXTERNAL, "status": "unavailable"}


@pytest.mark.parametrize("state", ["changed", "missing"])
def test_source_does_not_return_unverified_local_text(
    database: Path, indexed: GraphDTO, state: str,
) -> None:
    source = Path(indexed.rootPath or "") / "café.py"
    if state == "changed":
        source.write_text("not indexed\n")
    else:
        source.unlink()
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        result = navigation.source(BREW, max_lines=10, start_line=None)
    assert result["source"] == {"status": state, "path": "café.py"}


def test_revision_rejects_stale_graph_after_reindex(
    database: Path, indexed: GraphDTO, tmp_path: Path,
) -> None:
    with repository_service(database) as repositories:
        replacement = {"nodes": [], "edges": []}
        current = repositories.save_folder(tmp_path, replacement)
    assert current.repositoryId == indexed.repositoryId
    assert current.graphRevision != indexed.graphRevision
    with pytest.raises(NavigationError, match="Stale graph revision"):
        with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database):
            pytest.fail("Stale revision was accepted")
    with navigation_service(indexed.repositoryId, current.graphRevision, path=database) as navigation:
        assert navigation.find("brew", limit=10)["nodes"] == []
        assert navigation.overview()["roots"] == []


def test_repository_scoping_and_name_resolution(
    database: Path, indexed: GraphDTO, tmp_path: Path,
) -> None:
    other_root = tmp_path / "other"
    other_root.mkdir()
    other_artifact = artifact(other_root)
    other_artifact["nodes"] = other_artifact["nodes"][:2]
    other_artifact["edges"] = []
    other_artifact["nodes"][1]["name"] = "foreign_only"
    other_artifact["nodes"][1]["properties"]["cyclomaticComplexity"] = 99
    other_artifact["diagnostics"] = [
        {"severity": "error", "path": "café.py", "language": "python", "message": "foreign diagnostic"},
    ]
    with repository_service(database) as repositories:
        other = repositories.save_folder(other_root, other_artifact)
        name = next(project.name for project in repositories.list() if project.id == other.repositoryId)
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        assert navigation.find("foreign_only", limit=10)["nodes"] == []
        assert navigation.show(BREW)["node"]["metrics"]["cyclomaticComplexity"] == 8
        assert len(navigation.overview()["roots"]) == 2
    with navigation_service(name.upper(), other.graphRevision, path=database) as navigation:
        shown = navigation.show(BREW)
        assert shown["repositoryId"] == other.repositoryId
        assert shown["node"]["name"] == "foreign_only"
        assert shown["node"]["metrics"]["cyclomaticComplexity"] == 99
        assert [row["message"] for row in shown["diagnostics"]] == ["foreign diagnostic"]
        assert navigation.children(FILE, limit=10, offset=0)["nodes"][0]["name"] == "foreign_only"
        assert navigation.context(TraversalRequest(BREW, "both", ["CALLS"], 10, 20, 20))["edges"] == []
        with pytest.raises(NavigationError, match="Node not found"):
            navigation.show(GRIND)


def test_missing_node_and_unindexed_project(database: Path, indexed: GraphDTO, tmp_path: Path) -> None:
    with navigation_service(indexed.repositoryId, indexed.graphRevision, path=database) as navigation:
        with pytest.raises(NavigationError, match="Node not found"):
            navigation.show("missing")
        with pytest.raises(NavigationError, match="Node not found"):
            navigation.path(PathRequest("missing", TraversalRequest(BREW, "out", ["CALLS"], 3, 20, 20)))
    with repository_service(database) as repositories:
        unindexed = repositories.register({"name": "unindexed", "location": str(tmp_path / "unindexed")})
    with pytest.raises(NavigationError, match="no normalized graph"):
        with navigation_service(unindexed.id, None, path=database):
            pytest.fail("Unindexed project was accepted")
