"""Service workflows cross the real transaction and normalized-storage boundary."""

from copy import deepcopy
from pathlib import Path
from time import time
from typing import Any

import pytest

from atlas.domain.repositories import RepositoryError
from atlas.services.factories import repository_service
from atlas.services.repositories import analyze_folder
from tests.cli.command_scenarios import make_artifact


def test_registration_commits_trimmed_values_and_duplicate_recovery(database: Path) -> None:
    started = int(time() * 1000)
    with repository_service(database) as service:
        assert service.list() == []
        first = service.register({"name": "  Coffee  ", "location": "  /coffee  "})
        assert (first.name, first.location, first.importedAt) == ("Coffee", "/coffee", None)
        assert started <= first.createdAt <= int(time() * 1000)
        with pytest.raises(RepositoryError, match="already exists") as error:
            service.register({"name": "cOFFEE", "location": "/another"})
        assert error.value.status == 409
        second = service.register({"name": "Tea", "location": "/tea"})
    with repository_service(database) as service:
        assert {row.id for row in service.list()} == {first.id, second.id}
        assert service.get_architecture(first.id) is None
        assert service.get_report_facts(first.id) is None
        with pytest.raises(RepositoryError, match="no indexed graph") as error:
            service.report("coffee")
        assert error.value.status == 409


@pytest.mark.parametrize("value,message", [
    (None, "Expected an object"), ([], "Expected an object"),
    ({}, "name is required"), ({"name": 12}, "name is required"),
    ({"name": " "}, "name is required"),
    ({"name": "x" * 201}, "name must be at most 200"),
    ({"name": "Coffee", "location": None}, "location is required"),
    ({"name": "Coffee", "location": " "}, "location is required"),
    ({"name": "Coffee", "location": "x" * 4097}, "location must be at most 4096"),
])
def test_invalid_registration_leaves_no_rows(database: Path, value: Any, message: str) -> None:
    with repository_service(database) as service:
        with pytest.raises(RepositoryError, match=message) as error:
            service.register(value)
        assert error.value.status == 400
    with repository_service(database) as service:
        assert service.list() == []


def test_registration_accepts_exact_limits(database: Path) -> None:
    with repository_service(database) as service:
        row = service.register({"name": "x" * 200, "location": "y" * 4096})
    with repository_service(database) as service:
        assert service.list() == [row]


@pytest.mark.parametrize("method", ["get_architecture", "get_report_facts", "report", "index"])
@pytest.mark.parametrize("scenario", [(" ", 400), ("x" * 201, 400), ("missing", 404)])
def test_read_and_index_errors_do_not_write(database: Path, method: str, scenario: tuple[str, int]) -> None:
    identifier, status = scenario
    with repository_service(database) as service:
        with pytest.raises(RepositoryError) as error:
            if method == "index":
                service.index(identifier, Path("not-analyzed"))
            else:
                getattr(service, method)(identifier)
        assert error.value.status == status
        assert service.list() == []


def test_save_reuses_canonical_location_and_replaces_graph(database: Path, tmp_path: Path) -> None:
    artifact = make_artifact(tmp_path, circular_imports=True)
    started = int(time() * 1000)
    with repository_service(database) as service:
        first = service.save_folder(tmp_path, artifact)
        assert started <= first.importedAt <= int(time() * 1000)
        assert started <= service.list()[0].createdAt <= int(time() * 1000)
    with repository_service(database) as service:
        assert service.get_architecture(first.repositoryId) == first
        facts = service.get_report_facts(first.repositoryId)
        assert facts is not None
        assert len(facts.nodes) == 3 and len(facts.imports) == 2
        assert service.report(f" {tmp_path.name.upper()} ")["summary"]["files"] == 2
        replacement = service.save_folder(tmp_path / "child" / "..", make_artifact(tmp_path, empty=True))
    with repository_service(database) as service:
        assert replacement.repositoryId == first.repositoryId
        assert replacement.graphRevision != first.graphRevision
        assert started <= replacement.importedAt <= int(time() * 1000)
        assert replacement.stats.nodes == replacement.stats.edges == 0
        assert len(service.list()) == 1
        assert service.list()[0].importedAt == replacement.importedAt
        facts = service.get_report_facts(first.repositoryId)
        assert facts is not None
        assert facts.nodes == facts.imports == facts.edges == facts.diagnostics == []


def test_save_avoids_name_collisions_and_remote_locations(database: Path, tmp_path: Path) -> None:
    root = tmp_path / "Coffee"
    with repository_service(database) as service:
        remote = service.register({"name": "coffee", "location": "https://example.test/Coffee"})
        service.register({"name": "Coffee (2)", "location": "/elsewhere"})
        graph = service.save_folder(root, make_artifact(root))
    with repository_service(database) as service:
        saved = next(row for row in service.list() if row.id == graph.repositoryId)
        assert (saved.name, saved.location) == ("Coffee (3)", str(root))
        assert service.get_architecture(remote.id) is None


@pytest.mark.parametrize("existing", [False, True])
def test_failed_graph_write_rolls_back_registration_and_previous_graph(
    database: Path, tmp_path: Path, existing: bool,
) -> None:
    good = make_artifact(tmp_path)
    with repository_service(database) as service:
        before = service.save_folder(tmp_path, good) if existing else None
    broken = deepcopy(good)
    # Duplicate node keys fail after the graph header and replacement deletes execute.
    broken["nodes"].append(deepcopy(broken["nodes"][0]))
    with pytest.raises(RepositoryError) as error:
        with repository_service(database) as service:
            service.save_folder(tmp_path, broken)
    assert error.value.status == 500
    with repository_service(database) as service:
        if before is None:
            assert service.list() == []
        else:
            assert service.get_architecture(before.repositoryId) == before
            facts = service.get_report_facts(before.repositoryId)
            assert facts is not None and len(facts.nodes) == 2


def test_index_analyzes_source_and_preserves_last_graph_on_failure(database: Path, tmp_path: Path) -> None:
    source = tmp_path / "coffee.py"
    source.write_text("def brew(cups):\n    return cups + 1\n")
    with repository_service(database) as service:
        row = service.register({"name": "Coffee", "location": str(tmp_path)})
        first = service.index(" COFFEE ", tmp_path)
    with repository_service(database) as service:
        report = service.report("coffee")
        assert report["summary"]["files"] == 1
        facts = service.get_report_facts(row.id)
        assert facts is not None and facts.mutationCandidates
        with pytest.raises((OSError, ValueError)):
            service.index("Coffee", tmp_path / "missing")
    with repository_service(database) as service:
        assert service.get_architecture(row.id) == first
        source.write_text("def pour():\n    return 0\n")
        updated = service.index("coffee", tmp_path)
        assert updated.graphRevision != first.graphRevision
        facts = service.get_report_facts(row.id)
        assert facts is not None
        assert "pour" in {node.name for node in facts.nodes}
        assert "brew" not in {node.name for node in facts.nodes}


def test_analyze_folder_does_not_create_database(tmp_path: Path) -> None:
    (tmp_path / "coffee.py").write_text("def brew():\n    return 1\n")
    artifact = analyze_folder(tmp_path)
    assert artifact["stats"]["files"] == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == ["coffee.py"]
