"""Shared synthetic ledger values; integration tests use source fixtures."""

import base64
from hashlib import sha256
from pathlib import Path

from atlas.domain.mutation import MutationScope, MutationSession, MutationSite, MutationSource, MutationSpan, MutationTrialInput

SOURCE = b"def accept(amount, minimum):\n    return amount >= minimum\n"


def ledger_session(root: Path) -> MutationSession:
    digest = sha256(SOURCE).hexdigest()
    site = MutationSite(
        site_id="site-1", path="payments.py", language="python", kind="comparison",
        expression="amount >= minimum", context=SOURCE.decode(), callable="accept",
        span=MutationSpan(start_byte=39, end_byte=56, start_line=2, start_column=12, end_line=2, end_column=29),
        original_file_hash=digest,
    )
    return MutationSession(
        session_id="session-1", created_at="2026-01-01T00:00:00+00:00", root=str(root),
        scope=MutationScope(mode="folder", folders=["."]),
        sources=[MutationSource(path="payments.py", language="python", original_file_hash=digest, content_base64=base64.b64encode(SOURCE).decode())],
        sites=[site],
    )


def trial_input(digest: str | None = None, outcome: str = "survived") -> MutationTrialInput:
    return MutationTrialInput.model_validate({
        "schema_version": 1, "hypothesis": "Exact minimum must be accepted", "patch": "- amount >= minimum\n+ amount > minimum\n",
        "outcome": outcome, "explanation": "Unchanged tests passed; restored original bytes",
        "baseline": {"command": "pytest", "exit_code": 0, "duration_seconds": 1, "log_reference": "baseline.log"},
        "mutant": {"command": "pytest", "exit_code": 0, "duration_seconds": 1, "log_reference": "mutant.log"},
        "source_identity": {
            "original_file_hash": digest or sha256(SOURCE).hexdigest(),
            "mutant_file_hash": sha256(SOURCE.replace(b">=", b">")).hexdigest(),
            "restored_file_hash": digest or sha256(SOURCE).hexdigest(),
        },
    })
