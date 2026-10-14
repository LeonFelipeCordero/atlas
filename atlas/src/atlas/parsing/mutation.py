"""Raw-byte mutation syntax extraction, independent of metrics adapters.

Predicates: Python if/elif/while, assert, conditional expressions, comprehension
filters and match guards; JS/TS/TSX if/while/do/for and ternaries. Comparisons
include Python membership/identity and JS relational/equality operators (including
in/instanceof). Logical sites include and/or and &&/||, not unary not or ??
operators. Switch values and match patterns are not boolean predicates and are
reported as unsupported condition shapes. Literal text/comments and TS type syntax
are excluded; runtime string interpolations are traversed. Callable regions include
functions, methods and lambdas, not classes.
"""

import hashlib
import json
import posixpath
from typing import Literal

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from ..domain.mutation import (
    CallableRegion,
    MutationDiagnostic,
    MutationExtraction,
    MutationSite,
    MutationSpan,
)

Kind = Literal["predicate", "comparison", "logical"]
LANGUAGES = frozenset({"python", "javascript", "typescript", "tsx"})
CALLABLES = frozenset({
    "function_definition", "lambda", "function_declaration", "function_expression",
    "generator_function_declaration", "generator_function", "arrow_function",
    "method_definition",
})
CONDITION_FIELDS = frozenset({
    "if_statement", "elif_clause", "while_statement", "do_statement",
    "for_statement", "ternary_expression",
})
EXCLUDED = frozenset({
    "comment", "string_literal", "regex",
    "type_annotation", "type_arguments", "type_parameters", "type_alias_declaration",
    "interface_declaration", "ambient_declaration", "abstract_method_signature",
    "method_signature", "function_signature", "call_signature", "construct_signature",
    "conditional_type", "mapped_type_clause", "type_predicate", "type_query",
    "implements_clause", "extends_type_clause",
})
COMPARISONS = frozenset({"==", "!=", "===", "!==", "<", "<=", ">", ">=", "in", "instanceof"})


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _diagnostic(path: str, code: str, message: str) -> MutationDiagnostic:
    return MutationDiagnostic(path=path, code=code, message=message)


def _errors(root: Node) -> list[Node]:
    errors: list[Node] = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node.is_error or node.is_missing:
            errors.append(node)
        pending.extend(reversed(node.children))
    return errors


def _overlaps(node: Node, errors: list[Node]) -> bool:
    return any(
        node.start_byte < error.end_byte and error.start_byte < node.end_byte
        or error.is_missing and node.start_byte <= error.start_byte <= node.end_byte
        for error in errors
    )


def _unwrap(node: Node) -> Node:
    while node.type == "parenthesized_expression" and len(node.named_children) == 1:
        node = node.named_children[0]
    return node


def _predicate(node: Node, language: str) -> tuple[bool, Node | None]:
    if node.type in CONDITION_FIELDS:
        # A JS for(;;) intentionally has no predicate.
        condition = node.child_by_field_name("condition")
        if condition is not None and condition.type == "empty_statement":
            condition = None
        return node.type != "for_statement" or condition is not None, condition
    if language != "python":
        return False, None
    children = [child for child in node.named_children if child.type != "comment"]
    if node.type in {"assert_statement", "if_clause"}:
        return True, children[0] if children else None
    if node.type == "conditional_expression":
        return True, children[1] if len(children) == 3 else None
    return False, None


def _expression_kind(node: Node, source: bytes) -> Kind | None:
    if node.type == "comparison_operator":
        return "comparison"
    if node.type == "boolean_operator":
        return "logical"
    if node.type != "binary_expression":
        return None
    operator = node.child_by_field_name("operator")
    value = _text(operator, source) if operator is not None else ""
    if value in COMPARISONS:
        return "comparison"
    return "logical" if value in {"&&", "||"} else None


def _callable_name(node: Node, source: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return _text(name, source)
    parent = node.parent
    if parent is not None and parent.type in {"variable_declarator", "assignment", "pair"}:
        target = parent.child_by_field_name("name") or parent.child_by_field_name("left")
        target = target or parent.child_by_field_name("key")
        if target is not None:
            return _text(target, source)
    return "<lambda>" if node.type == "lambda" else "<anonymous>"


def _span(node: Node) -> MutationSpan:
    return MutationSpan(
        start_byte=node.start_byte, end_byte=node.end_byte,
        start_line=node.start_point.row + 1, start_column=node.start_point.column + 1,
        end_line=node.end_point.row + 1, end_column=node.end_point.column + 1,
    )


def _site(
    path: str, language: str, source: bytes, file_hash: str,
    node: Node, kind: Kind, owner: str | None, context: str,
) -> MutationSite:
    span = _span(node)
    identity = json.dumps(
        [path, language, file_hash, kind, span.model_dump()],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return MutationSite(
        site_id=hashlib.sha256(identity).hexdigest(), path=path, language=language,
        kind=kind, expression=_text(node, source), context=context,
        callable=owner, span=span, original_file_hash=file_hash,
    )


def _node_sites(
    node: Node, language: str, source: bytes, path: str,
    diagnostics: list[MutationDiagnostic],
) -> list[tuple[Kind, Node]]:
    sites: list[tuple[Kind, Node]] = []
    expected, predicate = _predicate(node, language)
    if predicate is not None:
        sites.append(("predicate", _unwrap(predicate)))
    elif expected:
        diagnostics.append(_diagnostic(
            path, "unsupported-condition",
            f"Unsupported {node.type} condition at byte {node.start_byte}.",
        ))
    if node.type in {"switch_statement", "match_statement"}:
        diagnostics.append(_diagnostic(
            path, "unsupported-condition",
            f"{node.type} patterns are not boolean predicates (byte {node.start_byte}).",
        ))
    kind = _expression_kind(node, source)
    if kind is not None:
        sites.append((kind, node))
    return sites


def _ownership(
    node: Node, source: bytes, path: str, owner: str | None, names: tuple[str, ...],
) -> tuple[str | None, tuple[str, ...], CallableRegion | None]:
    if node.type in {"class_definition", "class_declaration", "class"}:
        name = node.child_by_field_name("name")
        names += (_text(name, source) if name is not None else "<class>",)
    if node.type not in CALLABLES:
        return owner, names, None
    names += (_callable_name(node, source),)
    owner = f"{path}::{'.'.join(names)}@{node.start_byte}"
    return owner, names, CallableRegion(
        identity=owner, start_byte=node.start_byte, end_byte=node.end_byte,
    )


def _extract(
    root: Node, path: str, language: str, source: bytes, errors: list[Node],
) -> MutationExtraction:
    result = MutationExtraction()
    file_hash = hashlib.sha256(source).hexdigest()
    seen: set[tuple[Kind, int, int]] = set()
    contexts: dict[str, str] = {}
    lines = source.decode("utf-8").splitlines()
    pending: list[tuple[Node, str | None, tuple[str, ...]]] = [(root, None, ())]
    while pending:
        node, owner, names = pending.pop()
        if node.type in EXCLUDED or node.is_error or node.is_missing:
            continue
        owner, names, region = _ownership(node, source, path, owner, names)
        if region is not None:
            result.callables.append(region)
            contexts[region.identity] = _text(node, source)
        for kind, candidate in _node_sites(node, language, source, path, result.diagnostics):
            key = (kind, candidate.start_byte, candidate.end_byte)
            if key not in seen and not _overlaps(candidate, errors):
                context = contexts.get(owner or "") or "\n".join(lines[max(0, candidate.start_point.row - 2):candidate.end_point.row + 3])
                result.sites.append(_site(path, language, source, file_hash, candidate, kind, owner, context))
                seen.add(key)
        pending.extend((child, owner, names) for child in reversed(node.named_children))
    result.sites.sort(key=lambda site: (site.span.start_byte, site.span.end_byte, site.kind))
    return result


def extract_mutation_sites(path: str, language: str, source: bytes) -> MutationExtraction:
    """Extract snapshot identities and exclusive raw-byte spans without re-encoding.

    Paths are normalized lexically to POSIX spelling; callers supply project-relative
    paths. Identities are deterministic within a snapshot, not across source edits.
    Valid UTF-8 is required. Sites touching parser recovery are conservatively skipped;
    healthy regions of a partially malformed file can still produce sites.
    """
    path = posixpath.normpath(path)
    if language not in LANGUAGES:
        return MutationExtraction(diagnostics=[_diagnostic(
            path, "unsupported-language", f"Mutation extraction does not support {language!r}.",
        )])
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as error:
        return MutationExtraction(diagnostics=[_diagnostic(
            path, "invalid-encoding", f"Source is not UTF-8 at byte {error.start}.",
        )])
    root = get_parser(language).parse(source).root_node
    errors = _errors(root)
    # Recovery may truncate an otherwise valid-looking condition (e.g. `if x > :`).
    # Exclude its immediate container too, except the whole-file root.
    recovery = [
        error.parent if error.parent is not None and error.parent != root else error
        for error in errors
    ]
    result = _extract(root, path, language, source, recovery)
    result.diagnostics.extend(_diagnostic(
        path, "parse-error",
        f"Parser {'missing token' if error.is_missing else 'error region'} at bytes "
        f"{error.start_byte}:{error.end_byte}; recovery-container sites skipped.",
    ) for error in errors)
    return result
