"""Conservative generic resolution without language-specific receiver hooks."""

from tree_sitter import Node

from ...syntax import text
from .resolution_policy import ResolutionAdapter


def receiver_coverage(languages, dedicated) -> dict[str, dict[str, object]]:
    """JSON-serializable inventory for every supplied importer catalog entry."""
    return {
        language: {
            "status": "dedicated" if language in dedicated else "generic",
            "hooks": [],
            "verification": "not_verified_here",
            "limitations": "Dedicated policy" if language in dedicated else "Unresolved-only receiver fallback; no grammar hooks verified.",
        }
        for language in sorted(languages)
    }


def unwrapped(node: Node | None) -> Node | None:
    while node is not None and node.type == "parenthesized_expression" and len(node.named_children) == 1:
        node = node.named_children[0]
    return node


class GenericResolution(ResolutionAdapter):
    """No blanket name matching: unknown grammars retain no receiver bindings."""

    def __init__(self, language: str = ""):
        self.language = language

    def call_target(self, node):
        callee, receiver = super().call_target(unwrapped(node))
        return callee, unwrapped(receiver)

    def receiver_class_allowed(self, syntax, callee, member):
        return self.receiver_type_allowed(syntax, text(callee), member)
