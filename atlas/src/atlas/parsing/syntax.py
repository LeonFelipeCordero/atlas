"""Shared grammar extraction syntax, declarations, imports, calls and inheritance."""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from ..domain.models import SourceFile
from ..syntax import field, text, walk


def modifier_metadata(
    node: Node, visibility_words: frozenset[str]
) -> tuple[str | None, list[str]]:
    """Return optional visibility and annotation text from direct modifiers.

    Recognize visibility modifier nodes and the adapter's visibility words.
    """
    modifiers = next(
        (child for child in node.named_children if child.type == "modifiers"), None
    )
    visibility = None
    decorators: list[str] = []
    for child in modifiers.children if modifiers is not None else []:
        value = text(child)
        if child.type == "visibility_modifier" or value in visibility_words:
            visibility = value
        if "annotation" in child.type:
            decorators.append(value)
    return visibility, decorators


CALL_NODE_TYPES = frozenset(
    {
        "call",
        "call_expression",
        "function_call",
        "invocation_expression",
        "method_invocation",
        "new_expression",
        "object_creation_expression",
        "remote_call",
    }
)
REFERENCES = frozenset({"method_reference", "callable_reference"})
FALLBACK_CALL_TYPES = CALL_NODE_TYPES | REFERENCES


def relationship(
    site: tuple[Node, int, bool, tuple[Node, ...]],
) -> Literal["CALLS", "REFERENCES"]:
    """Classify method/callable references separately from invocation sites."""
    return "REFERENCES" if site[0].type in REFERENCES else "CALLS"


__all__ = [
    "CALL_NODE_TYPES",
    "REFERENCES",
    "CallSite",
    "CallTarget",
    "call_member",
    "call_target",
    "normalize_call",
    "call_sites",
]

CallSite = tuple[Node, int, bool, tuple[Node, ...]]
CallTarget = tuple[str | None, bool, str | None]


def call_member(target: Node) -> str:
    """Return stripped member text, falling back to the complete target text."""
    member = field(target, "property", "attribute", "field", "name", "method", "right")
    return text(member or target).strip()


def _reference_target(node: Node) -> tuple[str | None, bool, str | None]:
    parts = [child for child in node.named_children if child.type != "type_arguments"]
    if not parts:
        return None, False, None
    constructor = any(child.type == "new" for child in node.children)
    qualifier = text(parts[0]) if len(parts) > 1 or constructor else None
    return "new" if constructor else text(parts[-1]), not qualifier, qualifier


def call_target(
    node: Node, member_name: Callable[[Node], str] = call_member
) -> CallTarget:
    """Return target name, bare-name flag, and optional syntactic qualifier.

    Handle constructor references and dotted/scoped names without resolution;
    return (None, False, None) when no callee node exists.
    """
    if node.type in REFERENCES:
        return _reference_target(node)
    target = _callee_node(node)
    if target is None:
        return None, False, None
    bare = _bare_call(node, target)
    object_node = field(node, "object", "receiver")
    raw = text(object_node) + "." + text(target) if object_node else text(target)
    if re.fullmatch(r"([\w$]+(?:\.|::)[\w.$:]+)", raw):
        qualifier, _, terminal = raw.rpartition("::" if "::" in raw else ".")
        return terminal, False, qualifier
    return member_name(target) or None, bare, None


def _callee_node(node: Node) -> Node | None:
    target = field(
        node, "function", "callee", "target", "name", "method", "constructor", "type"
    ) or next(iter(node.named_children), None)
    if target is None:
        return None
    if target.type in {
        "generic_function", "template_function", "parameterized_expression"
    }:
        return field(target, "function", "name", "expression") or next(
            iter(target.named_children), target
        )
    return target


def _bare_call(node: Node, target: Node) -> bool:
    receiver = field(node, "object", "receiver", "scope")
    return (
        receiver is None
        and target.type in {"identifier", "simple_identifier", "type_identifier"}
        and not target.named_children
    )


def normalize_call(site: CallSite) -> CallTarget:
    """Extract the site's target without using offset or synthetic-scope data."""
    return call_target(site[0])


def call_sites(
    root: Node, node_types: frozenset[str] | set[str] = FALLBACK_CALL_TYPES
) -> Iterator[CallSite]:
    """Yield matching nodes with zero offset and no synthetic payload context."""
    for node in walk(root):
        if node.type in node_types:
            yield node, 0, False, ()


def metadata(node: Node) -> tuple[str | None, list[str]]:
    """Return visibility and annotations using the shared visibility vocabulary."""
    return modifier_metadata(
        node, frozenset({"public", "private", "protected", "internal", "pub"})
    )


@dataclass(frozen=True)
class DeclarationCarrier:
    node: Node
    name: str | None = None
    kind: str | None = None
    decorators: tuple[str, ...] = ()


def named_carrier(node: Node) -> DeclarationCarrier:
    """Keep the declaration node and its name field, or None when unnamed."""
    name = node.child_by_field_name("name")
    return DeclarationCarrier(node, text(name) if name is not None else None)


def callback_carrier(node: Node, binding: str | None = None) -> DeclarationCarrier:
    """Mark a function carrier, preferring a nonempty binding to its own name."""
    name = node.child_by_field_name("name")
    return DeclarationCarrier(
        node, binding or (text(name) if name is not None else None), "function"
    )


def _expression_children(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type != "comment"]


def _callback_value(node: Node) -> Node | None:
    parent = node.parent
    while parent is not None and parent.type == "parenthesized_expression":
        if _expression_children(parent) != [node]:
            return None
        node, parent = parent, parent.parent
    return node


def _callback_parent(node: Node) -> Node | None:
    parent = node.parent
    if parent is None or parent.type not in {
        "variable_declarator",
        "assignment_expression",
        "pair",
    }:
        return None
    value_field = "right" if parent.type == "assignment_expression" else "value"
    value = parent.child_by_field_name(value_field)
    if value is None or value.id != node.id:
        return None
    return parent


def callback_binding(node: Node) -> str | None:
    """Name a callback assigned as a value; other parent shapes remain anonymous."""
    value = _callback_value(node)
    if value is None:
        return None
    parent = _callback_parent(value)
    if parent is None:
        return None
    name_field = {"pair": "key", "assignment_expression": "left"}.get(
        parent.type, "name"
    )
    name = parent.child_by_field_name(name_field)
    if name is None:
        return None
    return text(name.child_by_field_name("property") or name)


@dataclass(frozen=True)
class ParsedSyntax:
    """Source and its reusable syntax tree; standalone extraction may omit the tree."""

    source: SourceFile
    root: Node | None = None

    def tree(self) -> Node:
        """Reuse the supplied root or parse source bytes without caching the result.

        Parser lookup and parsing failures propagate.
        """
        return self.root if self.root is not None else get_parser(
            self.source.language
        ).parse(self.source.source).root_node


@dataclass(frozen=True)
class ImportPolicy:
    node_type: str | None
    accept: Callable[[Node], bool] | None = None


def supplement_imports(
    syntax: ParsedSyntax, imports: list[tuple[str, int]], policy: ImportPolicy
) -> list[tuple[str, int]]:
    """Add accepted AST imports with one-based lines, sorted by source line.

    Deduplicate additions by stripped text and line; preserve native entries.
    Return the original list without parsing when the policy has no node type.
    """
    if policy.node_type is None:
        return imports
    return _merge_imports(syntax.tree(), imports, policy)


def _merge_imports(
    root: Node, imports: list[tuple[str, int]], policy: ImportPolicy
) -> list[tuple[str, int]]:
    seen = {(value.strip(), line) for value, line in imports}
    result = imports.copy()
    for node in walk(root):
        if node.type != policy.node_type:
            continue
        if policy.accept is not None and not policy.accept(node):
            continue
        value, line = text(node).rstrip(), node.start_point.row + 1
        if (value.strip(), line) in seen:
            continue
        result.append((value, line))
        seen.add((value.strip(), line))
    return sorted(result, key=lambda entry: entry[1])


BODY_NODES = frozenset(
    {
        "class_body",
        "interface_body",
        "field_declaration_list",
        "declaration_list",
        "block",
        "statement_block",
        "function_body",
    }
)
NAME_NODES = frozenset(
    {
        "identifier",
        "type_identifier",
        "namespace_identifier",
        "scoped_identifier",
        "scoped_type_identifier",
        "qualified_identifier",
        "attribute",
        "member_expression",
        "nested_type_identifier",
        "generic_type",
        "template_type",
        "user_type",
        "simple_identifier",
        "property_identifier",
        "nested_identifier",
        "subscript",
        "constructor_invocation",
        "call_expression",
    }
)


@dataclass(frozen=True)
class InheritancePolicy:
    clauses: frozenset[str]
    complete_header: bool = False
    superclass_field: str | None = None
    heritage_clause: str | None = None
    base_name: Callable[[Node], str | None] | None = None


# Other language-pack grammars still use the historical broad fallback.
DEFAULT_POLICY = InheritancePolicy(
    frozenset(
        {
            "superclass",
            "super_interfaces",
            "extends_interfaces",
            "extends_type_clause",
            "extends_clause",
            "implements_clause",
            "base_class_clause",
            "delegation_specifier",
        }
    ),
    superclass_field="superclasses",
    heritage_clause="class_heritage",
)


def _base_target(node: Node) -> Node | None:
    if node.type in {"subscript", "call_expression", "constructor_invocation"}:
        return field(node, "value", "function") or next(iter(node.named_children), None)
    return field(node, "name", "type") or next(iter(node.named_children), None)


def _base_components(node: Node, policy: InheritancePolicy) -> str:
    parts = []
    for child in node.children:
        part = text(child) if child.type in {".", "::"} else _base_name(child, policy)
        parts.append(part or "")
    return "".join(parts)


def _base_name(node: Node, policy: InheritancePolicy) -> str | None:
    override = policy.base_name(node) if policy.base_name else None
    if override is not None:
        return override
    if node.type not in NAME_NODES:
        return None
    if node.type in {
        "subscript",
        "call_expression",
        "constructor_invocation",
        "generic_type",
        "template_type",
    }:
        target = _base_target(node)
        return _base_name(target, policy) if target else None
    if not node.named_children:
        return text(node)
    return _base_components(node, policy) or None


def _clause_names(node: Node, policy: InheritancePolicy) -> list[str]:
    if node.type in {
        "type_arguments",
        "type_argument_list",
        "template_argument_list",
        "value_arguments",
        "access_specifier",
    }:
        return []
    name = _base_name(node, policy)
    if name:
        return [name]
    names = []
    for child in node.named_children:
        names.extend(_clause_names(child, policy))
    return names


@dataclass(frozen=True)
class DeclarationHeader:
    language: str
    kind: str
    signature: str


def inheritance_names(
    header: DeclarationHeader, policy: InheritancePolicy = DEFAULT_POLICY
) -> list[str]:
    """Extract syntactic base names from type headers, excluding body contents.

    Policies can retry incomplete headers with an empty body. Return [] for
    unsupported kinds, empty signatures, or parser lookup/parsing failures.
    """
    if header.kind not in {"class", "interface", "struct", "trait"} or not header.signature:
        return []
    try:
        root = get_parser(header.language).parse(header.signature.encode()).root_node
        if root.has_error and policy.complete_header:
            completed = (
                get_parser(header.language).parse((header.signature + " {}").encode()).root_node
            )
            if not completed.has_error:
                root = completed
    except Exception:
        return []
    return _header_names(root, policy)


def _superclass_names(node: Node, policy: InheritancePolicy) -> list[str]:
    bases = field(node, policy.superclass_field) if policy.superclass_field else None
    if bases is None:
        return []
    return [name for base in bases.named_children if (name := _base_name(base, policy))]


def _has_inheritance_clause(node: Node, policy: InheritancePolicy) -> bool:
    return any(child.type in policy.clauses for child in node.named_children)


def _is_inheritance_clause(node: Node, policy: InheritancePolicy) -> bool:
    if node.type in policy.clauses:
        return True
    return node.type == policy.heritage_clause and not _has_inheritance_clause(
        node, policy
    )


def _header_names(root: Node, policy: InheritancePolicy) -> list[str]:
    names: list[str] = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node.type in BODY_NODES:
            continue
        names.extend(_superclass_names(node, policy))
        if _is_inheritance_clause(node, policy):
            names.extend(_clause_names(node, policy))
            continue
        pending.extend(reversed(node.named_children))
    return names
