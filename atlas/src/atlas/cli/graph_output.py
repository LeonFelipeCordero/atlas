"""CLI-only labels for targets whose identity the index could not resolve.

Stored external nodes conflate missing and ambiguous declarations with outside
dependencies. They cannot prove a target is external. Keep their stable keys
for lookup compatibility, but do not expose that storage label as a conclusion.
"""

from typing import Any


def graph_output(value: Any) -> Any:
    """Project navigation JSON without changing stored facts or UI responses."""
    if isinstance(value, list):
        return [graph_output(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: graph_output(item) for key, item in value.items()}
    if result.get("level") == "external":
        result["level"] = "unresolved"
        _unresolved_identity(result)
    if result.get("reason") == "external_unresolved_or_ambiguous":
        result["reason"] = "unresolved_or_ambiguous"
    return result


def _unresolved_identity(result: dict) -> None:
    if "stableKey" not in result:
        return
    result.update(type="unresolved", external=False, unresolved=True)
    qualified_name = result.get("qualifiedName")
    if isinstance(qualified_name, str) and qualified_name.startswith("external:"):
        result["qualifiedName"] = "unresolved:" + qualified_name.removeprefix("external:")
