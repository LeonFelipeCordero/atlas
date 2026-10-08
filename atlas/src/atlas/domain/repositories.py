"""Transport-independent repository and graph values; no ORM types escape storage."""

from typing import Any, Protocol

from pydantic import BaseModel


class RepositoryError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class RepositoryDTO(BaseModel):
    id: str
    name: str
    location: str
    createdAt: int
    importedAt: int | None


class GraphDTO(BaseModel):
    repositoryId: str
    artifact: dict[str, Any]
    importedAt: int


class RepositoryProtocol(Protocol):
    def register(self, name: str, location: str) -> RepositoryDTO: ...

    def list(self) -> list[RepositoryDTO]: ...

    def exists(self, identifier: str) -> bool: ...

    def resolve(self, name: str) -> str | None: ...

    def graph(self, identifier: str) -> GraphDTO | None: ...

    def save(self, identifier: str, artifact: dict[str, Any]) -> GraphDTO: ...

    def save_new(self, name: str, location: str, artifact: dict[str, Any]) -> GraphDTO: ...
