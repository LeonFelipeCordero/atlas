"""SQLAlchemy repository; owns transactions and returns only domain DTOs."""

from __future__ import annotations

from time import time
from typing import Any
from uuid import uuid4

from atlas.domain.repositories import GraphDTO, RepositoryDTO, RepositoryError
from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError

from .graph_records import (
    decorator_records,
    diagnostic_records,
    edge_records,
    file_records,
    graph_metadata,
    metric_records,
    node_records,
    symbol_records,
    validate_parentage,
)
from .graph_queries import GraphReadRepository
from .models import (
    Base,
    GraphDiagnosticRow,
    GraphEdgeRow,
    GraphFileRow,
    GraphNodeDecoratorRow,
    GraphNodeMetricRow,
    GraphNodeRow,
    GraphSymbolRow,
    RepositoryGraphRow,
    RepositoryRow,
)


def _repository_dto(row: RepositoryRow, imported_at: int | None) -> RepositoryDTO:
    return RepositoryDTO(
        id=row.id,
        name=row.name,
        location=row.location,
        createdAt=row.created_at,
        importedAt=imported_at,
    )


class RepositoryStore(GraphReadRepository):
    def register(self, name: str, location: str) -> RepositoryDTO:
        self.session.rollback()
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
            select(RepositoryRow, case(
                (RepositoryGraphRow.graph_revision.is_not(None), RepositoryGraphRow.imported_at),
                else_=None,
            ))
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

    def save_new(self, name: str, location: str, artifact: dict[str, Any]) -> GraphDTO:
        self.session.rollback()
        row = RepositoryRow(
            id=str(uuid4()), name=name, location=location, created_at=int(time() * 1000)
        )
        # _save() flushes the registration and commits the whole graph together.
        try:
            self.session.add(row)
            return self._save(row.id, artifact)
        except Exception:
            self.session.rollback()
            raise

    def save(self, identifier: str, artifact: dict[str, Any]) -> GraphDTO:
        # End orchestration reads before promoting a stale WAL snapshot to a write.
        self.session.rollback()
        return self._save(identifier, artifact)

    def _save(self, identifier: str, artifact: dict[str, Any]) -> GraphDTO:
        imported_at = int(time() * 1000)
        try:
            validate_parentage(artifact)
            values = {
                "imported_at": imported_at,
                "graph_revision": uuid4().hex,
                **graph_metadata(artifact),
            }
            statement = insert(RepositoryGraphRow).values(repository_id=identifier, **values)
            statement = statement.on_conflict_do_update(
                index_elements=[RepositoryGraphRow.repository_id],
                set_={name: statement.excluded[name] for name in values},
            )
            self.session.execute(statement)
            self._replace_graph(identifier, artifact)
            row = self.session.get(RepositoryGraphRow, identifier, populate_existing=True)
            assert row is not None
            result = self._graph_summary(row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def _replace_graph(self, identifier: str, artifact: dict[str, Any]) -> None:
        self.session.execute(delete(GraphEdgeRow).where(GraphEdgeRow.repository_id == identifier))
        self.session.execute(delete(GraphNodeRow).where(GraphNodeRow.repository_id == identifier))
        self.session.execute(delete(GraphDiagnosticRow).where(GraphDiagnosticRow.repository_id == identifier))
        self._insert_records(GraphNodeRow, node_records(identifier, artifact))
        self._insert_records(GraphFileRow, file_records(identifier, artifact))
        self._insert_records(GraphSymbolRow, symbol_records(identifier, artifact))
        self._insert_records(GraphNodeMetricRow, metric_records(identifier, artifact))
        self._insert_records(GraphNodeDecoratorRow, decorator_records(identifier, artifact))
        self._insert_records(GraphEdgeRow, edge_records(identifier, artifact))
        self._insert_records(GraphDiagnosticRow, diagnostic_records(identifier, artifact))

    def _insert_records(self, entity: type[Base], records: list[dict[str, Any]]) -> None:
        if records:
            self.session.execute(insert(entity), records)
