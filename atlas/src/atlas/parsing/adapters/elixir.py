"""Elixir extraction hooks."""

from collections.abc import Iterator

from tree_sitter import Node

from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    call_target,
    InheritancePolicy,
)


from .base import LanguageAdapter

from ...language_syntax import DECLARATIONS, _declaration_head
from ...syntax import field, text, walk

QUERY = "\n(anonymous_function) @definition.function\n"


CALLBACK_TYPES = frozenset({"anonymous_function"})


CALL_TYPES = frozenset({"call", "remote_call"})


INHERITANCE = InheritancePolicy(frozenset())


def declaration(node: Node) -> DeclarationCarrier:
    """Mark anonymous functions as callbacks; keep other declaration names."""
    if node.type == "anonymous_function":
        return callback_carrier(node, callback_binding(node))
    return named_carrier(node)


NONCALLS = DECLARATIONS | {
    "defmodule",
    "defprotocol",
    "defimpl",
    "alias",
    "import",
    "use",
    "require",
    "if",
    "unless",
    "case",
    "cond",
    "with",
    "for",
    "receive",
    "try",
}


def _target(node: Node) -> str:
    target = field(node, "target") if node.type == "call" else None
    return text(target) if target is not None and target.type == "identifier" else ""


def _noncall(node: Node) -> bool:
    if _target(node) in NONCALLS:
        return True
    parent = node.parent
    while parent is not None:
        if _target(parent) in DECLARATIONS:
            head = _declaration_head(parent)
            return bool(
                head is not None
                and head.start_byte <= node.start_byte
                and node.end_byte <= head.end_byte
            )
        parent = parent.parent
    return False


def _pipeline_target(node: Node) -> bool:
    parent = node.parent
    return bool(
        parent is not None
        and parent.type == "binary_operator"
        and field(parent, "right") == node
        and any(child.type == "|>" for child in parent.children)
    )


def elixir_call_target(site: CallSite) -> CallTarget:
    """Treat pipeline RHS identifiers as bare calls; otherwise use shared syntax."""
    node = site[0]
    if node.type == "identifier":
        return text(node), True, None  # Zero-explicit-argument pipeline RHS.
    return call_target(node)


def elixir_call_sites(root: Node) -> Iterator[CallSite]:
    """Yield calls and pipeline RHS identifiers, excluding forms and def heads."""
    for node in walk(root):
        if node.type == "identifier":
            if _pipeline_target(node):
                yield node, 0, False, ()
            continue
        if node.type in CALL_TYPES and not _noncall(node):
            yield node, 0, False, ()


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=elixir_call_sites,
    inheritance_policy=INHERITANCE,
    normalize_call=elixir_call_target,
)
