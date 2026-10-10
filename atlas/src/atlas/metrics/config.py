"""Flat, optional project check limits; omitted keys inherit these defaults."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CheckConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

    maxFileLines: int | None = Field(default=600, ge=0)
    maxFunctionLines: int | None = Field(default=100, ge=0)
    maxParameters: int | None = Field(default=3, ge=0)
    maxWeightedComplexity: int | None = Field(default=8, ge=0)
    maxDecisionDepth: int | None = Field(default=3, ge=0)
    maxNestedLoops: int | None = Field(default=0, ge=0)
    maxCircularImportGroups: int | None = Field(default=0, ge=0)
    maxChangeImpact: int | None = Field(default=None, ge=0)
    maxInstability: float | None = Field(default=None, ge=0, le=1)


def load_config(root: Path) -> CheckConfig:
    """Read only the analyzed folder's atlas.json; absence means defaults."""
    path = root / "atlas.json"
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CheckConfig()
    try:
        return CheckConfig.model_validate_json(source)
    except ValidationError as error:
        raise ValueError(f"Invalid {path}: {error}") from error
