"""SQLAlchemy repository; owns transactions and returns only domain DTOs."""

import json
from time import time
from typing import Any
from uuid import uuid4

from atlas.domain.repositories import GraphDTO, RepositoryDTO, RepositoryError
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import RepositoryGraphRow, RepositoryRow


def _repository_dto(row: RepositoryRow, imported_at: int | None) -> RepositoryDTO:
    return RepositoryDTO(
        id=row.id,
        name=row.name,
        location=row.location,
        createdAt=row.created_at,
        importedAt=imported_at,
    )


class RepositoryStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, name: str, location: str) -> RepositoryDTO:
        row = RepositoryRow(
            id=str(uuid4()), name=name, location=location, created_at=int(time() * 1000)
        )
        try:
            self.session.add(row)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            if "repositories_name_unique" in str(error) or "repositories.name" in str(
                error
            ):
                raise RepositoryError(
                    "A repository with this name already exists", 409
                ) from error
            raise
        except Exception:
            self.session.rollback()
            raise
        return _repository_dto(row, None)

    def list(self) -> list[RepositoryDTO]:
        rows = self.session.execute(
            select(RepositoryRow, RepositoryGraphRow.imported_at)
            .outerjoin(
                RepositoryGraphRow, RepositoryRow.id == RepositoryGraphRow.repository_id
            )
            .order_by(RepositoryRow.created_at, RepositoryRow.id)
        ).all()
        return [_repository_dto(row, imported_at) for row, imported_at in rows]

    def exists(self, identifier: str) -> bool:
        return self.session.get(RepositoryRow, identifier) is not None

    def resolve(self, name: str) -> str | None:
        row = self.session.scalar(
            select(RepositoryRow).where(
                func.lower(RepositoryRow.name) == func.lower(name)
            )
        )
        return row.id if row else None

    def graph(self, identifier: str) -> GraphDTO | None:
        row = self.session.get(RepositoryGraphRow, identifier)
        return (
            GraphDTO(
                repositoryId=identifier,
                artifact=json.loads(row.artifact),
                importedAt=row.imported_at,
            )
            if row
            else None
        )

    def save_new(self, name: str, location: str, artifact: dict[str, Any]) -> GraphDTO:
        row = RepositoryRow(
            id=str(uuid4()), name=name, location=location, created_at=int(time() * 1000)
        )
        # save() flushes the pending registration and commits both writes together.
        self.session.add(row)
        return self.save(row.id, artifact)

    def save(self, identifier: str, artifact: dict[str, Any]) -> GraphDTO:
        imported_at = int(time() * 1000)
        payload = json.dumps(artifact, ensure_ascii=False, separators=(",", ":"))
        statement = insert(RepositoryGraphRow).values(
            repository_id=identifier, artifact=payload, imported_at=imported_at
        )
        statement = statement.on_conflict_do_update(
            index_elements=[RepositoryGraphRow.repository_id],
            set_={
                "artifact": statement.excluded.artifact,
                "imported_at": statement.excluded.imported_at,
            },
        )
        try:
            self.session.execute(statement)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return GraphDTO(
            repositoryId=identifier, artifact=artifact, importedAt=imported_at
        )
