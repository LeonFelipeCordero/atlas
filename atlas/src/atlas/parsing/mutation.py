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
from dataclasses import dataclass

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from ..domain.mutation import (
    CallableRegion,
    MutationDiagnostic,
    MutationExtraction,
    MutationKind,
    MutationSite,
    MutationSpan,
)

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


def _python_predicate(node: Node) -> tuple[bool, Node | None]:
    children = [child for child in node.named_children if child.type != "comment"]
    if node.type in {"assert_statement", "if_clause"}:
        return True, children[0] if children else None
    if node.type == "conditional_expression":
        return True, children[1] if len(children) == 3 else None
    return False, None


def _predicate(node: Node, language: str) -> tuple[bool, Node | None]:
    if node.type in CONDITION_FIELDS:
        # A JS for(;;) intentionally has no predicate.
        condition = node.child_by_field_name("condition")
        if condition is not None and condition.type == "empty_statement":
            condition = None
        return node.type != "for_statement" or condition is not None, condition
    return _python_predicate(node) if language == "python" else (False, None)


def _expression_kind(node: Node, source: bytes) -> MutationKind | None:
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
    if parent is not None and parent.type in {"variable_declarator", "assignment", "pair", "field_definition", "public_field_definition"}:
        target = parent.child_by_field_name("name") or parent.child_by_field_name("left")
        target = target or parent.child_by_field_name("key") or parent.child_by_field_name("property")
        if target is not None:
            return _text(target, source)
    return "<lambda>" if node.type == "lambda" else "<anonymous>"


def _span(node: Node) -> MutationSpan:
    return MutationSpan(
        start_byte=node.start_byte, end_byte=node.end_byte,
        start_line=node.start_point.row + 1, start_column=node.start_point.column + 1,
        end_line=node.end_point.row + 1, end_column=node.end_point.column + 1,
    )


@dataclass(frozen=True)
class _FileContext:
    path: str
    language: str
    source: bytes
    file_hash: str
    lines: list[str]

    def nearby_text(self, node: Node) -> str:
        return "\n".join(self.lines[max(0, node.start_point.row - 2):node.end_point.row + 3])


@dataclass(frozen=True)
class _Owner:
    identity: str | None = None
    names: tuple[str, ...] = ()
    context: str = ""


def _site(file: _FileContext, candidate: tuple[MutationKind, Node], owner: _Owner) -> MutationSite:
    kind, node = candidate
    span = _span(node)
    identity = json.dumps(
        [file.path, file.language, file.file_hash, kind, span.model_dump()],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return MutationSite(
        site_id=hashlib.sha256(identity).hexdigest(), path=file.path, language=file.language,
        kind=kind, expression=_text(node, file.source),
        context=owner.context or file.nearby_text(node),
        callable=owner.identity, span=span, original_file_hash=file.file_hash,
    )


def _node_sites(
    node: Node, file: _FileContext, diagnostics: list[MutationDiagnostic],
) -> list[tuple[MutationKind, Node]]:
    sites: list[tuple[MutationKind, Node]] = []
    expected, predicate = _predicate(node, file.language)
    if predicate is not None:
        sites.append(("predicate", _unwrap(predicate)))
    elif expected:
        diagnostics.append(_diagnostic(
            file.path, "unsupported-condition",
            f"Unsupported {node.type} condition at byte {node.start_byte}.",
        ))
    if node.type in {"switch_statement", "match_statement"}:
        diagnostics.append(_diagnostic(
            file.path, "unsupported-condition",
            f"{node.type} patterns are not boolean predicates (byte {node.start_byte}).",
        ))
    kind = _expression_kind(node, file.source)
    if kind is not None:
        sites.append((kind, node))
    return sites


def _callable_region(node: Node) -> Node:
    return node.parent if node.parent is not None and node.parent.type == "decorated_definition" else node


def _ownership(node: Node, file: _FileContext, owner: _Owner) -> _Owner:
    if node.type == "decorator" and node.parent is not None:
        definition = node.parent.child_by_field_name("definition")
        if definition is not None and definition.type in CALLABLES:
            return _ownership(definition, file, owner)
    names = owner.names
    if node.type in {"class_definition", "class_declaration", "abstract_class_declaration", "class"}:
        name = node.child_by_field_name("name")
        names += (_text(name, file.source) if name is not None else "<class>",)
    if node.type not in CALLABLES:
        return _Owner(owner.identity, names, owner.context)
    names += (_callable_name(node, file.source),)
    identity = f"{file.path}::{'.'.join(names)}@{node.start_byte}"
    return _Owner(identity, names, _text(_callable_region(node), file.source))


class _Extractor:
    def __init__(self, file: _FileContext, errors: list[Node]) -> None:
        self.file = file
        self.errors = errors
        self.result = MutationExtraction()
        self.seen: set[tuple[MutationKind, int, int]] = set()

    def add_sites(self, node: Node, owner: _Owner) -> None:
        for candidate in _node_sites(node, self.file, self.result.diagnostics):
            kind, expression = candidate
            key = (kind, expression.start_byte, expression.end_byte)
            if key in self.seen or _overlaps(expression, self.errors):
                continue
            self.result.sites.append(_site(self.file, candidate, owner))
            self.seen.add(key)

    def visit(self, node: Node, owner: _Owner) -> list[tuple[Node, _Owner]]:
        if node.type in EXCLUDED or node.is_error or node.is_missing:
            return []
        owner = _ownership(node, self.file, owner)
        if node.type in CALLABLES:
            region = _callable_region(node)
            self.result.callables.append(CallableRegion(
                identity=owner.identity or "", start_byte=region.start_byte, end_byte=region.end_byte,
            ))
        self.add_sites(node, owner)
        return [(child, owner) for child in reversed(node.named_children)]

    def extract(self, root: Node) -> MutationExtraction:
        pending = [(root, _Owner())]
        while pending:
            node, owner = pending.pop()
            pending.extend(self.visit(node, owner))
        self.result.sites.sort(key=lambda site: (site.span.start_byte, site.span.end_byte, site.kind))
        return self.result


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
        decoded = source.decode("utf-8")
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
    file = _FileContext(path, language, source, hashlib.sha256(source).hexdigest(), decoded.splitlines())
    result = _Extractor(file, recovery).extract(root)
    result.diagnostics.extend(_diagnostic(
        path, "parse-error",
        f"Parser {'missing token' if error.is_missing else 'error region'} at bytes "
        f"{error.start_byte}:{error.end_byte}; recovery-container sites skipped.",
    ) for error in errors)
    return result
