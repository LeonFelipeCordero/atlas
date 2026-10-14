"""Transactional mutation storage; only domain values cross this boundary."""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.domain.mutation import MutationSession, MutationSite, MutationSource, MutationTrial
from atlas.domain.repositories import RepositoryError
from .database import repository_session
from .mutation_models import MutationSessionRow, MutationSiteRow, MutationSourceRow, MutationTrialRow


@contextmanager
def mutation_store(path: str | Path | None = None) -> Generator["MutationStore", None, None]:
    with repository_session(path) as session:
        yield MutationStore(session)


class MutationStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_session(self, value: MutationSession) -> None:
        """Insert one complete plan atomically; never update an existing snapshot."""
        metadata = value.model_dump_json(exclude={"sources", "sites"})
        self._session.add(MutationSessionRow(session_id=value.session_id, payload=metadata))
        self._session.flush()
        self._session.add_all([
            MutationSourceRow(session_id=value.session_id, path=source.path, ordinal=index, payload=source.model_dump_json())
            for index, source in enumerate(value.sources)
        ])
        self._session.flush()
        self._session.add_all([
            MutationSiteRow(session_id=value.session_id, site_id=site.site_id, path=site.path, ordinal=index, payload=site.model_dump_json())
            for index, site in enumerate(value.sites)
        ])
        self._session.commit()

    def get_session(self, session_id: str) -> MutationSession:
        row = self._session.get(MutationSessionRow, session_id)
        if row is None:
            raise RepositoryError(f"Unknown mutation session: {session_id}", 404)
        sources = self._session.scalars(select(MutationSourceRow).where(MutationSourceRow.session_id == session_id).order_by(MutationSourceRow.ordinal))
        sites = self._session.scalars(select(MutationSiteRow).where(MutationSiteRow.session_id == session_id).order_by(MutationSiteRow.ordinal))
        return MutationSession.model_validate({
            **json.loads(row.payload),
            "sources": [MutationSource.model_validate_json(source.payload) for source in sources],
            "sites": [MutationSite.model_validate_json(site.payload) for site in sites],
        })

    def append_trial(self, value: MutationTrial) -> None:
        self._session.add(MutationTrialRow(
            trial_id=value.trial_id, session_id=value.session_id, site_id=value.site_id,
            payload=value.model_dump_json(),
        ))
        self._session.commit()

    def trials(self, session_id: str) -> list[MutationTrial]:
        rows = self._session.scalars(select(MutationTrialRow).where(MutationTrialRow.session_id == session_id).order_by(MutationTrialRow.ordinal))
        return [MutationTrial.model_validate_json(row.payload) for row in rows]
