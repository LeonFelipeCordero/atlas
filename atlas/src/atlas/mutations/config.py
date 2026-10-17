"""Opt-in rule IDs; replacement tokens belong to the rule catalog."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .rules import validate_rules


class MutationTarget(BaseModel):
    """Explicit source globs and a trusted command, relative to the project root."""

    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

    sources: list[str] = Field(min_length=1)
    cwd: str = "."
    command: list[str] = Field(min_length=1)
    timeoutSeconds: int = Field(default=120, gt=0)

    @field_validator("sources", "command")
    @classmethod
    def nonempty_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Source patterns and command arguments must not be empty")
        return value

    @field_validator("sources")
    @classmethod
    def relative_patterns(cls, value: list[str]) -> list[str]:
        if any(pattern.startswith("/") or "\\" in pattern or ".." in pattern.split("/") for pattern in value):
            raise ValueError("Source patterns must be project-relative POSIX globs")
        return value


class MutationConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    rules: list[str] = Field(default_factory=list)
    targets: dict[str, MutationTarget] = Field(default_factory=dict)

    @field_validator("targets")
    @classmethod
    def selectable_names(cls, value: dict[str, MutationTarget]) -> dict[str, MutationTarget]:
        if any(not name or name != name.strip() or "," in name or name == "all" for name in value):
            raise ValueError("Target names must be nonempty, trimmed, contain no commas, and must not be 'all'")
        return value

    @field_validator("rules")
    @classmethod
    def supported_rules(cls, value: list[str]) -> list[str]:
        """Reject unknown rule IDs with ValueError; retain order and duplicates."""
        validate_rules(value)
        return value
