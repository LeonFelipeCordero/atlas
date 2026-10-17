"""Cross-repository storage and service composition contracts."""

from pathlib import Path

import pytest

from atlas.services.factories import navigation_service, repository_service
from atlas.domain.navigation import NavigationError
from tests.services.test_navigation import artifact, BREW


@pytest.mark.parametrize("variable", ["DATABASE_PATH", "XDG_DATA_HOME"])
def test_default_service_database_is_explicitly_sandboxed(
    database: Path, monkeypatch: pytest.MonkeyPatch, variable: str,
) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(database.parent.parent))
    if variable == "DATABASE_PATH":
        monkeypatch.setenv("DATABASE_PATH", str(database))
    with repository_service() as repositories:
        registered = repositories.register({"name": "Coffee", "location": "/coffee"})
    with repository_service(database) as repositories:
        assert repositories.list() == [registered]


def test_summary_and_report_facts_are_repository_scoped(database: Path, tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_artifact = artifact(first_root)
    second_artifact = artifact(second_root)
    second_artifact["nodes"][1]["properties"]["cyclomaticComplexity"] = 99
    second_artifact["nodes"][1]["startLine"] = 50
    second_artifact["diagnostics"] = [
        {"severity": "warning", "path": "café.py", "language": "python", "message": "warning only"},
    ]
    second_artifact["edges"] = []
    with repository_service(database) as repositories:
        first = repositories.save_folder(first_root, first_artifact)
        second = repositories.save_folder(second_root, second_artifact)
    with repository_service(database) as repositories:
        one = repositories.get_architecture(first.repositoryId)
        two = repositories.get_architecture(second.repositoryId)
        assert one is not None and two is not None
        assert (one.stats.nodes, one.stats.files, one.stats.symbols, one.stats.edges, one.stats.parseErrors) == (6, 1, 5, 4, 2)
        assert (two.stats.nodes, two.stats.files, two.stats.symbols, two.stats.edges, two.stats.parseErrors) == (6, 1, 5, 0, 0)
        facts = repositories.get_report_facts(first.repositoryId)
        assert facts is not None
        brew = next(node for node in facts.nodes if node.stableKey == BREW)
        assert (brew.startLine, brew.cyclomaticComplexity, brew.lineCount) == (2, 8, 3)
        assert len(facts.nodes) == 6
        assert len(facts.edges) == 4
        assert facts.imports == []
        assert [row["message"] for row in facts.diagnostics] == ["local diagnostic", "unrelated diagnostic"]
        file = next(node for node in facts.nodes if node.level == "file")
        assert file.startLine is None and file.cyclomaticComplexity is None


def test_navigation_selects_nearest_containing_local_project(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    with repository_service(database) as repositories:
        repositories.register({"name": "remote", "location": "https://example.test/project"})
        repositories.save_folder(outer, artifact(outer))
        selected = repositories.save_folder(inner, artifact(inner))
    monkeypatch.chdir(inner)
    with navigation_service(path=database) as navigation:
        assert navigation.overview()["repositoryId"] == selected.repositoryId
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NavigationError, match="No indexed project contains"):
        with navigation_service(path=database):
            pytest.fail("An unrelated folder selected a project")
    with pytest.raises(NavigationError, match="not found or ambiguous"):
        with navigation_service("missing", path=database):
            pytest.fail("An unknown project was accepted")
