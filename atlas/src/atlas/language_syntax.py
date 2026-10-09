"""Grammar helpers shared by extraction and metric policies."""

from tree_sitter import Node

from .syntax import field


DECLARATIONS = {
    "def",
    "defp",
    "defmacro",
    "defmacrop",
    "defguard",
    "defguardp",
    "defdelegate",
}


def _declaration_head(node: Node) -> Node | None:
    arguments = next(
        (child for child in node.named_children if child.type == "arguments"), None
    )
    head = _first_head(arguments)
    if (
        head is not None
        and head.type == "binary_operator"
        and any(child.type == "when" for child in head.children)
    ):
        return field(head, "left")
    return head


def _first_head(arguments: Node | None) -> Node | None:
    if arguments is None:
        return None
    return next(
        (child for child in arguments.named_children if child.type != "keywords"), None
    )


def _property_callable(node: Node) -> Node | None:
    annotation = field(node, "type")
    while annotation is not None and annotation.type in {
        "type_annotation",
        "parenthesized_type",
    }:
        annotation = next(iter(annotation.named_children), None)
    if annotation is None or annotation.type != "function_type":
        return None
    return annotation
