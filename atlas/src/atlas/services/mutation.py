"""Mutation ledger orchestration; never edits source or executes tests."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, get_args
from uuid import uuid4

from atlas.domain.mutation import MutationOutcome, MutationRepository, MutationSession, MutationSource, MutationTrial, MutationTrialInput
from atlas.domain.repositories import RepositoryError
from atlas.mutation.planning import plan_mutation


OUTCOMES = get_args(MutationOutcome)


def source_status(root: Path, source: MutationSource) -> str:
    """Read current source safely; matching bytes do not verify agent claims."""
    path = root / source.path
    try:
        if not path.resolve().is_relative_to(root.resolve()):
            return "unreadable"
        digest = sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return "missing"
    except (OSError, RuntimeError):
        return "unreadable"
    return "matches-session" if digest == source.original_file_hash else "differs"


def build_report(session: MutationSession, trials: list[MutationTrial]) -> dict[str, Any]:
    """Expose actionable metadata without duplicating stored source-file contents."""
    explored = {trial.site_id for trial in trials}
    return {
        **session.model_dump(mode="json", exclude={"sources"}),
        "sources": [
            {**source.model_dump(exclude={"content_base64"}), "current_source_status": source_status(Path(session.root), source)}
            for source in session.sources
        ],
        "provenance": "agent-reported",
        "trials": [trial.model_dump(mode="json") for trial in trials],
        "outcome_counts": {outcome: sum(trial.result.outcome == outcome for trial in trials) for outcome in OUTCOMES},
        "unexplored_sites": [site.site_id for site in session.sites if site.site_id not in explored],
    }


class MutationService:
    def __init__(self, repository: MutationRepository) -> None:
        self._repository = repository

    def plan(self, folders: tuple[Path, ...], base: str | None = None) -> dict[str, Any]:
        session = plan_mutation(folders, base)
        self._repository.save_session(session)
        return build_report(session, [])

    def record(self, session_id: str, site_id: str, result: MutationTrialInput) -> dict[str, Any]:
        session = self._repository.get_session(session_id)
        site = next((site for site in session.sites if site.site_id == site_id), None)
        if site is None:
            raise RepositoryError(f"Unknown site in mutation session: {site_id}", 404)
        if result.source_identity.original_file_hash != site.original_file_hash:
            raise ValueError("Trial original_file_hash does not match the session snapshot; create a new plan for changed source")
        source = next(source for source in session.sources if source.path == site.path)
        status = source_status(Path(session.root), source)
        trial = MutationTrial(
            trial_id=uuid4().hex, session_id=session_id, site_id=site_id,
            recorded_at=datetime.now(timezone.utc).isoformat(), result=result,
        )
        self._repository.append_trial(trial)
        return {**trial.model_dump(mode="json"), "current_source_status": status}

    def report(self, session_id: str) -> dict[str, Any]:
        session = self._repository.get_session(session_id)
        return build_report(session, self._repository.trials(session_id))
