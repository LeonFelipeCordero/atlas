"""Opt-in rule IDs; replacement tokens belong to the rule catalog."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .rules import validate_rules


class MutationConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    rules: list[str] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def supported_rules(cls, value: list[str]) -> list[str]:
        """Reject unknown rule IDs with ValueError; retain order and duplicates."""
        validate_rules(value)
        return value
