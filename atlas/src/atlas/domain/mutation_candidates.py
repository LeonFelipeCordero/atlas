"""Serializable raw-source mutation candidates, independent of persisted artifacts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

MutationKind = Literal["condition", "comparison", "logical", "arithmetic", "assignment"]


class MutationSpan(BaseModel):
    """Half-open byte offsets and one-based UTF-8 byte line/column positions."""

    model_config = ConfigDict(strict=True, frozen=True)

    startByte: int
    endByte: int
    startLine: int
    startColumn: int
    endLine: int
    endColumn: int


class MutationCallable(BaseModel):
    """Nearest enclosing callable's exact source region."""

    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    span: MutationSpan
    originalText: str


class MutationCandidate(BaseModel):
    """A condition expression or precise operator token eligible for mutation."""

    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    path: str
    language: str
    sourceHash: str
    kind: MutationKind
    operator: str | None = None
    span: MutationSpan
    expressionSpan: MutationSpan
    originalText: str
    expressionText: str
    callable: MutationCallable | None = None


class MutationCandidateDiagnostic(BaseModel):
    """An extraction limitation; never evidence of mutation execution."""

    model_config = ConfigDict(strict=True, frozen=True)

    path: str
    language: str
    code: str
    message: str
    span: MutationSpan | None = None


class MutationCandidateAnalysis(BaseModel):
    """Deterministically ordered candidates and extraction diagnostics."""

    model_config = ConfigDict(strict=True, frozen=True)

    candidates: list[MutationCandidate]
    diagnostics: list[MutationCandidateDiagnostic]
