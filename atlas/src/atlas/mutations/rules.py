"""Small, versioned syntactic rules; coverage is explicit, never type validity.

Python comparisons mutate one token in a chain, not the whole comparison.
Conditions, unary operators, coercion/type semantics and custom operators are
not rewritten. Rule IDs select fixed edits, never arbitrary source templates.
Elixir strict and truthy logical operators stay separate.
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
_NON_ELIXIR = tuple(language for language in _LANGUAGES if language != "elixir")
_STRICT_EQUALITY = ("javascript", "typescript", "tsx", "elixir")


def _rule(id: str, edit: tuple[MutationKind, str, str], languages: tuple[str, ...] = _LANGUAGES) -> MutationRule:
    kind, original, replacement = edit
    return MutationRule(id=id, kind=kind, mappings=tuple(
        RuleMapping(language=language, original=original, replacement=replacement)
        for language in languages
    ))


def _logical_rule(id: str, edit: tuple[str, str], python_edit: tuple[str, str]) -> MutationRule:
    original, replacement = edit
    return MutationRule(id=id, kind="logical", mappings=tuple(
        RuleMapping(language=language, original=python_edit[0] if language == "python" else original,
                    replacement=python_edit[1] if language == "python" else replacement)
        for language in _NON_ELIXIR
    ))


REGISTRY: tuple[MutationRule, ...] = (
    _rule("arithmetic.add-to-subtract", ("arithmetic", "+", "-")),
    _rule("arithmetic.subtract-to-add", ("arithmetic", "-", "+")),
    _rule("arithmetic.multiply-to-divide", ("arithmetic", "*", "/")),
    _rule("arithmetic.divide-to-multiply", ("arithmetic", "/", "*")),
    _rule("comparison.equal-to-not-equal", ("comparison", "==", "!=")),
    _rule("comparison.not-equal-to-equal", ("comparison", "!=", "==")),
    _rule("comparison.less-to-less-equal", ("comparison", "<", "<=")),
    _rule("comparison.less-equal-to-less", ("comparison", "<=", "<")),
    _rule("comparison.greater-to-greater-equal", ("comparison", ">", ">=")),
    _rule("comparison.greater-equal-to-greater", ("comparison", ">=", ">")),
    _rule("comparison.less-to-greater", ("comparison", "<", ">")),
    _rule("comparison.greater-to-less", ("comparison", ">", "<")),
    _rule("comparison.strict-equal-to-strict-not-equal", ("comparison", "===", "!=="), _STRICT_EQUALITY),
    _rule("comparison.strict-not-equal-to-strict-equal", ("comparison", "!==", "==="), _STRICT_EQUALITY),
    _logical_rule("logical.and-to-or", ("&&", "||"), ("and", "or")),
    _logical_rule("logical.or-to-and", ("||", "&&"), ("or", "and")),
    _rule("logical.strict-and-to-or", ("logical", "and", "or"), ("elixir",)),
    _rule("logical.strict-or-to-and", ("logical", "or", "and"), ("elixir",)),
    _rule("logical.truthy-and-to-or", ("logical", "&&", "||"), ("elixir",)),
    _rule("logical.truthy-or-to-and", ("logical", "||", "&&"), ("elixir",)),
    _rule("assignment.add-to-subtract", ("assignment", "+=", "-="), _NON_ELIXIR),
    _rule("assignment.subtract-to-add", ("assignment", "-=", "+="), _NON_ELIXIR),
    _rule("assignment.multiply-to-divide", ("assignment", "*=", "/="), _NON_ELIXIR),
    _rule("assignment.divide-to-multiply", ("assignment", "/=", "*="), _NON_ELIXIR),
)


def validate_rules(rules: list[str]) -> None:
    """Raise ValueError unless selections are a list of known string rule IDs.

    Accept an empty list and duplicates without changing the input.
    """
    if not isinstance(rules, list):
        raise ValueError("Mutation rules must be a list of rule IDs")
    catalog = {rule.id for rule in REGISTRY}
    for id in rules:
        if not isinstance(id, str) or id not in catalog:
            raise ValueError(f"Unknown mutation rule: {id}")
