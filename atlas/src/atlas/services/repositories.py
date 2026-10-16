"""Validation, repository orchestration and in-memory analysis."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlas.metrics.report import build_report
from atlas.domain.repositories import (
    GraphDTO,
    RepositoryDTO,
    RepositoryError,
    RepositoryProtocol,
    ReportFactsDTO,
)
from atlas.indexer import analyze_repository


def _required_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepositoryError(f"{field} is required", 400)
    result = value.strip()
    if len(result) > maximum:
        raise RepositoryError(f"{field} must be at most {maximum} characters", 400)
    return result


def analyze_folder(root: Path) -> dict[str, Any]:
    """Return a graph artifact dict from local analysis without opening a database.

    Propagate analysis failures; no saved graph is changed.
    """
    return asdict(analyze_repository(root))


class RepositoryService:
    """Accepts a repository implementation; exposes domain DTOs, never ORM objects."""

    def __init__(self, repository: RepositoryProtocol) -> None:
        self._repository = repository

    def register(self, input: Any) -> RepositoryDTO:
        """Validate/trim name and location, then persist and return a registration.

        Raise RepositoryError (400) for malformed input or excessive lengths;
        the store reports duplicate names as 409. Do not index the location.
        """
        if not isinstance(input, dict):
            raise RepositoryError("Expected an object with name and location", 400)
        name = _required_text(input.get("name"), "name", 200)
        location = _required_text(input.get("location"), "location", 4096)
        return self._repository.register(name, location)

    def list(self) -> list[RepositoryDTO]:
        """Return registered repositories and their latest normalized import times."""
        return self._repository.list()

    def get_architecture(self, identifier: str) -> GraphDTO | None:
        """Return a graph summary, or None for a registration not yet indexed.

        Validate/trim the repository ID; raise RepositoryError (400) for invalid
        IDs and 404 for missing registrations.
        """
        identifier = _required_text(identifier, "repositoryId", 200)
        if not self._repository.exists(identifier):
            raise RepositoryError("Repository not found", 404)
        return self._repository.graph(identifier)

    def get_report_facts(self, identifier: str) -> ReportFactsDTO | None:
        """Return normalized report facts, or None if not yet indexed.

        Validate/trim the repository ID; raise RepositoryError (400) for invalid
        IDs and 404 for missing registrations. Never expose the repository port.
        """
        identifier = _required_text(identifier, "repositoryId", 200)
        if not self._repository.exists(identifier):
            raise RepositoryError("Repository not found", 404)
        return self._repository.report_facts(identifier)

    def report(self, project_name: str) -> dict[str, Any]:
        """Build a report from saved facts for a case-insensitive project name.

        Raise RepositoryError for invalid names (400), missing registrations
        (404), or missing indexed graphs (409). Do not analyze local sources.
        """
        name = _required_text(project_name, "project name", 200)
        identifier = self._repository.resolve(name)
        if identifier is None:
            raise RepositoryError("Repository not found", 404)
        graph = self._repository.report_facts(identifier)
        if graph is None:
            raise RepositoryError("Repository has no indexed graph; run atlas index first", 409)
        return build_report(graph)

    def save_folder(self, root: Path, artifact: dict[str, Any]) -> GraphDTO:
        """Save an artifact by canonical local location and return its summary.

        Update an existing registration, or choose an unused folder-based name
        and register/save atomically. Ignore URL registrations; never analyze
        sources here. Store failures leave the previous saved graph intact.
        """
        root = root.expanduser().resolve()
        for project in self._repository.list():
            if "://" in project.location:
                continue
            if Path(project.location).expanduser().resolve() == root:
                return self._repository.save(project.id, artifact)
        base = root.name.strip()[:190] or "repository"
        name = base
        suffix = 2
        while self._repository.resolve(name) is not None:
            name = f"{base} ({suffix})"
            suffix += 1
        return self._repository.save_new(name, str(root), artifact)

    def index(self, project_name: str, root: Path) -> GraphDTO:
        """Analyze root, then replace the named project's graph and return a summary.

        Resolve the case-insensitive name, not the root location. Invalid names
        raise RepositoryError (400), missing projects 404. Analysis failures
        propagate before any save; the store commits the replacement atomically.
        """
        name = _required_text(project_name, "project name", 200)
        identifier = self._repository.resolve(name)
        if identifier is None:
            raise RepositoryError("Repository not found", 404)
        # Analyze first. Failed analysis cannot overwrite the previous graph.
        artifact = analyze_folder(Path(root))
        return self._repository.save(identifier, artifact)
