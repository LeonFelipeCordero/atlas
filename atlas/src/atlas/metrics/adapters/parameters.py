"""Shared grammar-backed parameter helpers; ambiguous headers stay unknown."""

from tree_sitter import Node

from ...syntax import field

COMMENTS = frozenset({"comment", "line_comment", "block_comment"})


def parameter_children(node: Node) -> list[Node]:
    """Return named parameter-container children without comment nodes."""
    return [child for child in node.named_children if child.type not in COMMENTS]


def parameter_node(node: Node, *types: str) -> Node | None:
    """Prefer parameter fields, then the first named child of a supplied grammar type."""
    return field(node, "parameters", "parameter") or next(
        (child for child in node.named_children if child.type in types), None
    )


def count_parameters(
    parameters: Node | None, excluded: frozenset[str] = frozenset()
) -> int | None:
    """Count non-comment children except excluded types; missing/error headers yield None."""
    if parameters is None or parameters.has_error:
        return None
    return sum(child.type not in excluded for child in parameter_children(parameters))
