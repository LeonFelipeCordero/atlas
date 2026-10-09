"""Small syntax-tree primitives shared by extraction and analysis."""

from collections.abc import Iterator

from tree_sitter import Node


def walk(root: Node) -> Iterator[Node]:
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.named_children))


def text(node: Node | None) -> str:
    return (
        (node.text or b"").decode("utf-8", errors="replace") if node is not None else ""
    )


def field(node: Node, *names: str) -> Node | None:
    return next(
        (
            child
            for name in names
            if (child := node.child_by_field_name(name)) is not None
        ),
        None,
    )
