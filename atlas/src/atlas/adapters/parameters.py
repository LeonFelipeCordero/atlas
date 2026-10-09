"""Shared grammar-backed parameter helpers; ambiguous headers stay unknown."""

from tree_sitter import Node

from ..extraction.syntax import field

COMMENTS = frozenset({"comment", "line_comment", "block_comment"})


def parameter_children(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type not in COMMENTS]


def parameter_node(node: Node, *types: str) -> Node | None:
    return field(node, "parameters", "parameter") or next(
        (child for child in node.named_children if child.type in types), None
    )


def count_parameters(
    parameters: Node | None, excluded: frozenset[str] = frozenset()
) -> int | None:
    if parameters is None or parameters.has_error:
        return None
    return sum(child.type not in excluded for child in parameter_children(parameters))
