"""Snapshot-bound mutation opportunities and agent-reported experiment contracts."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MutationValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MutationDiagnostic(MutationValue):
    path: str
    code: str
    message: str


class MutationSpan(MutationValue):
    """Zero-based exclusive byte offsets; one-based lines and byte columns."""

    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


class CallableRegion(MutationValue):
    identity: str
    start_byte: int
    end_byte: int


class MutationSite(MutationValue):
    site_id: str
    path: str
    language: str
    kind: Literal["predicate", "comparison", "logical"]
    expression: str
    context: str
    callable: str | None = None
    span: MutationSpan
    original_file_hash: str
    diff_relationship: str = "folder-scope"


class MutationExtraction(MutationValue):
    sites: list[MutationSite] = Field(default_factory=list)
    callables: list[CallableRegion] = Field(default_factory=list)
    diagnostics: list[MutationDiagnostic] = Field(default_factory=list)


class MutationScope(MutationValue):
    mode: Literal["folder", "git-diff"]
    folders: list[str]
    requested_base: str | None = None
    resolved_base: str | None = None


class MutationSource(MutationValue):
    path: str
    language: str
    original_file_hash: str
    content_base64: str
    deleted: bool = False


class MutationSession(MutationValue):
    schema_version: Literal[1] = 1
    extraction_version: Literal[1] = 1
    session_id: str
    created_at: str
    root: str
    scope: MutationScope
    sources: list[MutationSource]
    sites: list[MutationSite]
    limitations: list[MutationDiagnostic] = Field(default_factory=list)


class ExecutionEvidence(MutationValue):
    command: str = Field(min_length=1)
    exit_code: int | None
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    log_reference: str = Field(min_length=1)


class SourceIdentity(MutationValue):
    original_file_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    mutant_file_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    restored_file_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class MutationTrialInput(MutationValue):
    schema_version: Literal[1]
    hypothesis: str = Field(min_length=1)
    patch: str
    outcome: Literal["killed", "survived", "invalid", "timeout", "error", "skipped"]
    baseline: ExecutionEvidence | None = None
    mutant: ExecutionEvidence | None = None
    source_identity: SourceIdentity
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_required(self) -> "MutationTrialInput":
        if self.outcome == "skipped":
            return self
        if self.baseline is None:
            raise ValueError("Executed trials require baseline evidence")
        if self.outcome == "error":
            return self
        if not self.patch.strip() or self.mutant is None:
            raise ValueError("Executed trials require a patch and mutant evidence")
        if self.baseline.exit_code != 0:
            raise ValueError("Executed trials require a passing baseline")
        self._validate_source_identity()
        self._validate_outcome()
        return self

    def _validate_source_identity(self) -> None:
        if self.source_identity.mutant_file_hash is None or self.source_identity.restored_file_hash is None:
            raise ValueError("Executed trials require mutant and restored source hashes")

    def _validate_outcome(self) -> None:
        if self.mutant is None:
            return
        if self.outcome == "survived" and self.mutant.exit_code != 0:
            raise ValueError("Survived trials require a passing mutant run")
        if self.outcome == "killed" and self.mutant.exit_code in (0, None):
            raise ValueError("Killed trials require a failing mutant run; explain assertion evidence")


class MutationTrial(MutationValue):
    trial_id: str
    session_id: str
    site_id: str
    recorded_at: str
    provenance: Literal["agent-reported"] = "agent-reported"
    result: MutationTrialInput


class MutationRepository(Protocol):
    def save_session(self, value: MutationSession) -> None: ...

    def get_session(self, session_id: str) -> MutationSession: ...

    def append_trial(self, value: MutationTrial) -> None: ...

    def trials(self, session_id: str) -> list[MutationTrial]: ...
