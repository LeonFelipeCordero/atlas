"""Small, versioned syntactic rules; coverage is explicit, never type validity.

Python comparisons mutate one token in a chain, not the whole comparison.
Conditions, unary operators, coercion/type semantics and custom operators are
not rewritten. Empty selections select nothing; replacements are allowlists,
not source templates. Elixir strict and truthy logical operators stay separate.
"""

from pydantic import BaseModel, ConfigDict

from atlas.domain.mutation_candidates import MutationKind


class RuleMapping(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    language: str
    original: str
    replacement: str


class MutationRule(BaseModel):
    """Serializable coverage catalog, including exact language/token pairs."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    version: int = 1
    kind: MutationKind
    mappings: tuple[RuleMapping, ...]
    limitations: str = "Syntactic only; no type or runtime validity guarantee."


_LANGUAGES = ("python", "javascript", "typescript", "tsx", "java", "kotlin", "rust", "go", "elixir")


def _rule(id: str, edit: tuple[MutationKind, str, str], languages: tuple[str, ...] = _LANGUAGES) -> MutationRule:
    kind, original, replacement = edit
    return MutationRule(id=id, kind=kind, mappings=tuple(
        RuleMapping(language=language, original=original, replacement=replacement)
        for language in languages
    ))


REGISTRY: tuple[MutationRule, ...] = (
    _rule("arithmetic.add-to-subtract", ("arithmetic", "+", "-")),
    _rule("arithmetic.multiply-to-divide", ("arithmetic", "*", "/")),
    _rule("comparison.equal-to-not-equal", ("comparison", "==", "!=")),
    _rule("comparison.less-to-less-equal", ("comparison", "<", "<=")),
    _rule("comparison.strict-equal-to-strict-not-equal", ("comparison", "===", "!=="), ("javascript", "typescript", "tsx", "elixir")),
    MutationRule(id="logical.and-to-or", kind="logical", mappings=tuple(
        RuleMapping(language=language, original="and" if language == "python" else "&&", replacement="or" if language == "python" else "||")
        for language in _LANGUAGES if language != "elixir"
    )),
    _rule("logical.strict-and-to-or", ("logical", "and", "or"), ("elixir",)),
    _rule("logical.truthy-and-to-or", ("logical", "&&", "||"), ("elixir",)),
    _rule("assignment.add-to-subtract", ("assignment", "+=", "-="), tuple(language for language in _LANGUAGES if language != "elixir")),
)


def _validate_replacements(rule: MutationRule, replacements: list[str]) -> None:
    allowed = {mapping.replacement for mapping in rule.mappings}
    if not isinstance(replacements, list) or any(not isinstance(token, str) or token not in allowed for token in replacements):
        raise ValueError(f"Invalid replacements for {rule.id}; allowed: {sorted(allowed)}")


def validate_rules(rules: dict[str, list[str]]) -> None:
    """Raise ValueError for unknown IDs or replacements outside their catalog."""
    catalog = {rule.id: rule for rule in REGISTRY}
    for id, replacements in rules.items():
        if id not in catalog:
            raise ValueError(f"Unknown mutation rule: {id}")
        _validate_replacements(catalog[id], replacements)
