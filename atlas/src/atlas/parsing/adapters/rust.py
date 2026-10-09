"""Rust extraction hooks."""

import re

from collections.abc import Iterator


from itertools import chain


from tree_sitter import Node

from tree_sitter_language_pack import get_parser


from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    call_target,
    InheritancePolicy,
    modifier_metadata,
)


from .base import LanguageAdapter


from ...syntax import field, text, walk

QUERY = """
(closure_expression) @definition.function
(function_signature_item name: (identifier) @name) @definition.function
"""


CALLBACK_TYPES = frozenset({"closure_expression"})


CALL_TYPES = frozenset({"call_expression", "macro_invocation"})


IMPORT_NODE = "mod_item"


INHERITANCE = InheritancePolicy(frozenset())


def declaration(node: Node) -> DeclarationCarrier:
    if node.type == "closure_expression":
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    return modifier_metadata(node, frozenset({"pub"}))


def rust_module_import(node: Node) -> bool:
    """Only external module declarations are source dependencies, not inline bodies."""
    return field(node, "body") is None


def rust_call_target(site: CallSite) -> CallTarget:
    node, _, opaque, parents = site
    if node.type == "macro_invocation":
        return text(field(node, "macro")) + "!", False, None
    name, bare_target, qualifier = call_target(node)
    if not name:
        return name, bare_target, qualifier
    target = (qualifier or name).split("::")[0].split(".")[0]
    if opaque and not payload_unshadowed(node, target, parents):
        return name, False, None
    return name, bare_target, qualifier


def rust_call_sites(
    root: Node,
    offset: int = 0,
    opaque: bool = False,
    origin: Node | None = None,
    parents: tuple[Node, ...] = (),
) -> Iterator[CallSite]:
    origin = origin if origin is not None else root
    for node in walk(root):
        if node.type == "macro_invocation":
            yield node, offset, opaque, parents
            yield from _macro_sites(node, root, origin, parents, offset, opaque)
            continue
        if node.type in CALL_TYPES:
            yield node, offset, opaque, parents


def _macro_sites(
    node: Node,
    root: Node,
    origin: Node,
    parents: tuple[Node, ...],
    offset: int,
    opaque: bool,
) -> Iterator[CallSite]:
    for payload, shift in macro_payloads(node, origin, parents):
        enclosing = (root, *parents) if opaque else parents
        yield from rust_call_sites(payload, offset + shift, True, origin, enclosing)


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
    """Reject matching bindings in synthetic payloads without inferring local targets."""
    target = _payload_target(node)
    if target is not None and target.type == "field_expression":
        return False  # A synthetic object receiver is not a module namespace.
    return not any(
        _payload_binding(declaration, name)
        for declaration in _walk_roots((_root(node), *parents))
    )


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=rust_call_sites,
    import_node=IMPORT_NODE,
    inheritance_policy=INHERITANCE,
    normalize_call=rust_call_target,
    accept_import=rust_module_import,
    metadata=metadata,
)
