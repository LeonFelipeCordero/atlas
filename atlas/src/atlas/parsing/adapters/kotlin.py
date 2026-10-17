"""Kotlin extraction hooks."""

from tree_sitter import Node


from .base import LanguageAdapter


from ..syntax import (
    DeclarationCarrier,
    callback_carrier,
    callback_binding,
    named_carrier,
    CallSite,
    CallTarget,
    call_target,
    call_member,
    call_sites as shared_call_sites,
    InheritancePolicy,
    modifier_metadata,
)

from ...syntax import text

QUERY = """
(package_header (identifier) @name) @definition.module
(companion_object) @definition.class
[(lambda_literal) (anonymous_function)] @definition.function
"""


CALLBACK_TYPES = frozenset({"lambda_literal", "anonymous_function"})


CALL_TYPES = frozenset({"call_expression", "callable_reference"})


IMPORT_NODE = "import_header"


def _base_name(node: Node) -> str | None:
    if node.type != "user_type":
        return None
    return (
        ".".join(
            text(child)
            for child in node.named_children
            if child.type == "type_identifier"
        )
        or None
    )


INHERITANCE = InheritancePolicy(
    frozenset({"delegation_specifier"}), complete_header=True, base_name=_base_name
)


def declaration(node: Node) -> DeclarationCarrier:
    """Normalize callbacks, function names, interfaces, and companion objects.

    Use 'Companion' for an unnamed companion object.
    """
    if node.type in {"lambda_literal", "anonymous_function"}:
        return callback_carrier(node, callback_binding(node))
    if node.type == "function_declaration":
        return DeclarationCarrier(node, _identifier_name(node, "simple_identifier"))
    return _type_declaration(node)


def _identifier_name(node: Node, kind: str) -> str | None:
    name = next((child for child in node.named_children if child.type == kind), None)
    return text(name) if name is not None else None


def _type_declaration(node: Node) -> DeclarationCarrier:
    carrier = named_carrier(node)
    if node.type == "companion_object" and carrier.name is None:
        name = _identifier_name(node, "type_identifier")
        return DeclarationCarrier(node, name if name is not None else "Companion")
    if node.type == "class_declaration" and any(
        child.type == "interface" for child in node.children
    ):
        return DeclarationCarrier(node, carrier.name, "interface")
    return carrier


def _member(target: Node) -> str:
    if target.type != "navigation_expression":
        return call_member(target)
    suffix = next(
        (
            child
            for child in reversed(target.named_children)
            if child.type == "navigation_suffix"
        ),
        None,
    )
    member = next(iter(suffix.named_children), None) if suffix else None
    return text(member or target).strip()


def normalize_call(site: CallSite) -> CallTarget:
    """Extract a target using Kotlin navigation suffixes for member names."""
    return call_target(site[0], _member)


def call_sites(root: Node):
    """Iterate Kotlin invocations and callable references."""
    return shared_call_sites(root, CALL_TYPES)


def metadata(node: Node) -> tuple[str | None, list[str]]:
    """Return explicit Kotlin visibility and annotations, including internal."""
    return modifier_metadata(
        node, frozenset({"public", "private", "protected", "internal"})
    )


ADAPTER = LanguageAdapter(
    declaration_query=QUERY,
    callback_types=CALLBACK_TYPES,
    normalize_declaration=declaration,
    call_sites=call_sites,
    import_node=IMPORT_NODE,
    inheritance_policy=INHERITANCE,
    normalize_call=normalize_call,
    metadata=metadata,
)
