"""Conservative Rust evaluating-macro payload parsing and shadow checks."""

import re
from collections.abc import Iterator
from itertools import chain

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from ..extraction.syntax import field, text, walk

EXPRESSION_MACROS = {
    "println",
    "print",
    "eprintln",
    "eprint",
    "format",
    "format_args",
    "write",
    "writeln",
    "dbg",
    "assert",
    "assert_eq",
    "assert_ne",
    "debug_assert",
    "debug_assert_eq",
    "debug_assert_ne",
    "vec",
    "panic",
}


def _root(node: Node) -> Node:
    while node.parent is not None:
        node = node.parent
    return node


def _qualified_macro_shadowed(declaration: Node, namespace: str) -> bool:
    if declaration.type == "mod_item" and text(field(declaration, "name")) == namespace:
        return True
    return bool(
        declaration.type in {"use_declaration", "extern_crate_declaration"}
        and re.search(rf"\b{re.escape(namespace)}\b", text(declaration))
        and not text(declaration).startswith(
            (f"use {namespace}::", f"extern crate {namespace};")
        )
    )


def _macro_shadowed(declaration: Node, parts: list[str], name: str) -> bool:
    if len(parts) > 1:
        return _qualified_macro_shadowed(declaration, parts[0])
    return bool(
        declaration.type == "macro_definition"
        and text(field(declaration, "name")) == name
        or declaration.type == "use_declaration"
        and (name in text(declaration) or "*" in text(declaration))
        and not text(declaration).startswith(("use std::", "use core::"))
    )


def _walk_roots(roots):
    return chain.from_iterable(walk(root) for root in roots)


def _evaluating(node: Node, origin: Node | None, parents: tuple[Node, ...]) -> bool:
    parts = text(field(node, "macro")).split("::")
    name = parts[-1]
    if (
        name not in EXPRESSION_MACROS
        or len(parts) > 1
        and parts[0] not in {"std", "core"}
    ):
        return False
    root = _root(node)
    roots = [root, *parents]
    if origin is not None and origin.id != root.id:
        roots.append(origin)
    return not any(
        _macro_shadowed(declaration, parts, name) for declaration in _walk_roots(roots)
    )


def _macro_tokens(node: Node) -> Node | None:
    tokens = next(
        (child for child in node.named_children if child.type == "token_tree"), None
    )
    return tokens if tokens is not None and len(tokens.text or b"") >= 2 else None


def macro_payloads(
    node: Node, origin: Node | None = None, parents: tuple[Node, ...] = ()
) -> Iterator[tuple[Node, int]]:
    """Only recognized evaluating macros expose candidate calls in valid Rust syntax."""
    if not _evaluating(node, origin, parents):
        return
    tokens = _macro_tokens(node)
    if tokens is None:
        return
    for prefix, suffix in (
        (b"fn __macro_arguments(){ [", b"]; }"),
        (b"fn __macro_arguments(){ ", b" }"),
    ):
        root = (
            get_parser("rust")
            .parse(prefix + (tokens.text or b"")[1:-1] + suffix)
            .root_node
        )
        if not root.has_error:
            yield root, tokens.start_byte + 1 - len(prefix)
            return


def _pattern_names(node: Node) -> set[str]:
    if node.type in {"identifier", "field_identifier"}:
        return {text(node)}
    return set().union(
        *(
            _pattern_names(child)
            for index, child in enumerate(node.children)
            if child.is_named
            and node.field_name_for_child(index) not in {"type", "path"}
        )
    )


def _named_binding(declaration: Node, name: str) -> bool:
    return (
        declaration.type
        in {
            "function_item",
            "mod_item",
            "struct_item",
            "enum_item",
            "const_item",
            "static_item",
        }
        and text(field(declaration, "name")) == name
    )


def _payload_binding(declaration: Node, name: str) -> bool:
    pattern = None
    if declaration.type in {"let_declaration", "for_expression", "match_arm"}:
        pattern = field(declaration, "pattern")
    if declaration.type in {"parameters", "closure_parameters"}:
        pattern = declaration
    if declaration.type == "use_declaration" and (
        re.search(rf"\b{re.escape(name)}\b", text(declaration))
        or "*" in text(declaration)
    ):
        return True
    if _named_binding(declaration, name):
        return True
    return pattern is not None and name in _pattern_names(pattern)


def _payload_target(node: Node) -> Node | None:
    target = field(node, "function")
    while target is not None and target.type == "generic_function":
        target = field(target, "function") or next(iter(target.named_children), None)
    return target


def payload_unshadowed(node: Node, name: str, parents: tuple[Node, ...] = ()) -> bool:
    """Reject matching bindings anywhere in a synthetic payload, never infer locals.

    This avoids treating a local closure/parameter as a top-level function without
    persisting synthetic AST scopes or assuming language-independent expansion.
    """
    target = _payload_target(node)
    if target is not None and target.type == "field_expression":
        return False  # A synthetic object receiver is not a module namespace.
    return not any(
        _payload_binding(declaration, name)
        for declaration in _walk_roots((_root(node), *parents))
    )
