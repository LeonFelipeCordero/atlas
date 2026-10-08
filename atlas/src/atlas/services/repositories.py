"""Validation, repository orchestration and in-memory analysis."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlas.domain.report import build_report
from atlas.domain.repositories import (
    GraphDTO,
    RepositoryDTO,
    RepositoryError,
    RepositoryProtocol,
)
from atlas.indexer import analyze_repository


def _required_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepositoryError(f"{field} is required", 400)
    result = value.strip()
    if len(result) > maximum:
        raise RepositoryError(f"{field} must be at most {maximum} characters", 400)
    return result


def _saved_folder(location: str) -> Path | None:
    if "://" in location:
        return None
    folder = Path(location).expanduser()
    # Legacy relative locations have no durable base; never match the CLI cwd.
    return folder.resolve() if folder.is_absolute() else None


def analyze_folder(root: Path) -> dict[str, Any]:
    """Analyze entirely in memory, without opening or creating a database."""
    return asdict(analyze_repository(root))


class RepositoryService:
    """Accepts a repository implementation; exposes domain DTOs, never ORM objects."""

    def __init__(self, repository: RepositoryProtocol) -> None:
        self.repository = repository

    def register(self, input: Any) -> RepositoryDTO:
        if not isinstance(input, dict):
            raise RepositoryError("Expected an object with name and location", 400)
        name = _required_text(input.get("name"), "name", 200)
        location = _required_text(input.get("location"), "location", 4096)
        if "://" not in location:
            location = str(Path(location).expanduser().resolve())
        return self.repository.register(name, location)

    def list(self) -> list[RepositoryDTO]:
        return self.repository.list()

    def get_architecture(self, identifier: str) -> GraphDTO | None:
        identifier = _required_text(identifier, "repositoryId", 200)
        if not self.repository.exists(identifier):
            raise RepositoryError("Repository not found", 404)
        return self.repository.graph(identifier)

    def report(self, project_name: str) -> dict[str, Any]:
        name = _required_text(project_name, "project name", 200)
        identifier = self.repository.resolve(name)
        if identifier is None:
            raise RepositoryError("Repository not found", 404)
        graph = self.repository.graph(identifier)
        if graph is None:
            raise RepositoryError("Repository has no indexed graph; run atlas index first", 409)
        return build_report(graph)

    def save_folder(self, root: Path, artifact: dict[str, Any]) -> GraphDTO:
        """Update by canonical location; otherwise register and save atomically."""
        root = root.expanduser().resolve()
        matches = [
            project for project in self.repository.list()
            if _saved_folder(project.location) == root
        ]
        if len(matches) > 1:
            raise RepositoryError("Multiple projects are registered for this folder; use a distinct local checkout for each project", 409)
        if matches:
            return self.repository.save(matches[0].id, artifact)
        base = root.name.strip()[:190] or "repository"
        name = base
        suffix = 2
        while self.repository.resolve(name) is not None:
            name = f"{base} ({suffix})"
            suffix += 1
        return self.repository.save_new(name, str(root), artifact)

    def index(self, project_name: str, root: Path) -> GraphDTO:
        name = _required_text(project_name, "project name", 200)
        identifier = self.repository.resolve(name)
        if identifier is None:
            raise RepositoryError("Repository not found", 404)
        # Analyze first. Failed analysis cannot overwrite the previous graph.
        artifact = analyze_folder(Path(root))
        return self.repository.save(identifier, artifact)
