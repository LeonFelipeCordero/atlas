"""Opt-in supported replacements, not arbitrary source templates."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .rules import validate_rules


class MutationConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    rules: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("rules")
    @classmethod
    def supported_rules(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        validate_rules(value)
        return value
