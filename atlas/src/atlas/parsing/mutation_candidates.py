"""Deterministic mutation sites from original bytes, not normalized Atlas syntax.

Adapters intentionally recognize expression nodes per grammar. Operators in types,
patterns, comments and literal text are not candidates. No source is executed.
Elixir conditions assume unqualified Kernel if/unless: only false/nil are falsey;
guards require true. Original operators retain strict and/or versus truthy &&/||.
Macro expansion, import resolution and custom operator semantics are not inferred.
"""

import hashlib
import json
from dataclasses import dataclass, field

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from atlas.domain.models import SourceFile
from atlas.syntax import text
from atlas.domain.mutation_candidates import (
    MutationCallable,
    MutationCandidate,
    MutationCandidateAnalysis,
    MutationKind,
    MutationSpan,
)

# These are grammar-specific allowlists, not a language-agnostic token search.
_EXPRESSIONS: dict[str, set[str]] = {
    "python": {"comparison_operator", "boolean_operator", "binary_operator", "not_operator", "unary_operator", "augmented_assignment"},
    "javascript": {"binary_expression", "unary_expression", "augmented_assignment_expression"},
    "typescript": {"binary_expression", "unary_expression", "augmented_assignment_expression"},
    "tsx": {"binary_expression", "unary_expression", "augmented_assignment_expression"},
    "java": {"binary_expression", "unary_expression", "assignment_expression"},
    "kotlin": {"comparison_expression", "equality_expression", "check_expression", "conjunction_expression", "disjunction_expression", "additive_expression", "multiplicative_expression", "prefix_expression", "assignment"},
    "rust": {"binary_expression", "unary_expression", "compound_assignment_expr"},
    "go": {"binary_expression", "unary_expression", "assignment_statement"},
    "elixir": {"binary_operator", "unary_operator"},
}
_CONDITIONS: dict[str, set[str]] = {
    "python": {"if_statement", "elif_clause", "while_statement", "conditional_expression", "if_clause", "assert_statement"},
    "javascript": {"if_statement", "while_statement", "do_statement", "for_statement", "ternary_expression"},
    "typescript": {"if_statement", "while_statement", "do_statement", "for_statement", "ternary_expression"},
    "tsx": {"if_statement", "while_statement", "do_statement", "for_statement", "ternary_expression"},
    "java": {"if_statement", "while_statement", "do_statement", "for_statement", "ternary_expression"},
    "kotlin": {"if_expression", "while_statement", "do_while_statement"},
    "rust": {"if_expression", "while_expression"},
    "go": {"if_statement", "for_clause", "for_statement"},
    "elixir": set(),
}
_CALLABLES: dict[str, set[str]] = {
    "python": {"function_definition", "lambda"},
    "javascript": {"function_declaration", "function_expression", "generator_function_declaration", "generator_function", "arrow_function", "method_definition"},
    "typescript": {"function_declaration", "function_expression", "generator_function_declaration", "generator_function", "arrow_function", "method_definition"},
    "tsx": {"function_declaration", "function_expression", "generator_function_declaration", "generator_function", "arrow_function", "method_definition"},
    "java": {"method_declaration", "constructor_declaration", "lambda_expression"},
    "kotlin": {"function_declaration", "anonymous_function", "lambda_literal"},
    "rust": {"function_item", "closure_expression"},
    "go": {"function_declaration", "method_declaration", "func_literal"},
    "elixir": {"anonymous_function"},
}
_EXCLUDED = {
    "comment", "line_comment", "block_comment", "regex", "regex_pattern",
    "type", "type_annotation", "type_arguments", "type_parameters", "type_alias_declaration",
    "interface_declaration", "ambient_declaration", "conditional_type", "mapped_type_clause",
    "type_predicate", "type_query", "implements_clause", "extends_type_clause",
    "type_spec", "type_constraint", "type_constraints", "where_clause",
    "const_parameter", "array_type", "literal_pattern", "range_pattern",
    "let_condition", "let_chain", "token_tree", "macro_definition", "when_condition",
}
_COMPARISONS = {"==", "!=", "===", "!==", "<", "<=", ">", ">=", "in", "not in", "is", "is not", "instanceof", "!in", "!is", "=~"}
_LOGICAL = {"and", "or", "not", "&&", "||", "!", "??", "andalso", "orelse"}
_ARITHMETIC = {"+", "-", "*", "/", "//", "%", "**"}
_ASSIGNMENT = {"+=", "-=", "*=", "/=", "//=", "%=", "**=", "&&=", "||=", "??="}


def _span(node: Node) -> MutationSpan:
    return MutationSpan(
        startByte=node.start_byte, endByte=node.end_byte,
        startLine=node.start_point.row + 1, startColumn=node.start_point.column + 1,
        endLine=node.end_point.row + 1, endColumn=node.end_point.column + 1,
    )


def _unwrap(node: Node) -> Node:
    while node.type in {"parenthesized_expression", "parenthesized_expression_list"} and len(node.named_children) == 1:
        node = node.named_children[0]
    return node


def _kind(operator: str) -> MutationKind | None:
    if operator in _COMPARISONS:
        return "comparison"
    if operator in _LOGICAL:
        return "logical"
    if operator in _ARITHMETIC:
        return "arithmetic"
    return "assignment" if operator in _ASSIGNMENT else None


def _operator_kind(operator: str, language: str, expression_type: str) -> MutationKind | None:
    if operator == "*" and language in {"rust", "go"} and expression_type == "unary_expression":
        return None  # Pointer dereference is not arithmetic multiplication.
    return _kind(operator)


def _operators(node: Node, language: str) -> list[tuple[MutationKind, Node]]:
    if node.type not in _EXPRESSIONS[language]:
        return []
    result: list[tuple[MutationKind, Node]] = []
    for i, token in enumerate(node.children):
        # Named operators may contain tokens; select only direct children.
        if token.is_named and token.type != "assignment_operator" and node.field_name_for_child(i) not in {"operator", "operators"}:
            continue
        operator = " ".join(text(token).split())
        kind = _operator_kind(operator, language, node.type)
        if kind is not None:
            result.append((kind, token))
    return result


def _condition(node: Node, language: str) -> Node | None:
    if language == "elixir":
        return _elixir_condition(node)
    if node.type not in _CONDITIONS[language]:
        return None
    condition = node.child_by_field_name("condition")
    if condition is not None:
        return None if condition.type in {"empty_statement", ";"} else _unwrap(condition)
    return _unfielded_condition(node, language)


def _python_condition(node: Node, children: list[Node]) -> Node | None:
    if node.type == "conditional_expression":
        return children[1] if len(children) == 3 else None
    if node.type in {"if_clause", "assert_statement"}:
        return children[0] if children else None
    return None


def _unfielded_condition(node: Node, language: str) -> Node | None:
    children = [child for child in node.named_children if "comment" not in child.type]
    if language == "python":
        return _python_condition(node, children)
    excluded = {
        ("kotlin", "while_statement"): {"control_structure_body"},
        ("kotlin", "do_while_statement"): {"control_structure_body"},
        ("go", "for_statement"): {"block", "for_clause", "range_clause"},
    }.get((language, node.type))
    if excluded is None:
        return None
    return next((child for child in children if child.type not in excluded), None)


def _elixir_guard(node: Node) -> bool:
    return text(node.child_by_field_name("operator")) == "when"


def _first_argument(node: Node) -> Node | None:
    arguments = next((child for child in node.named_children if child.type == "arguments"), None)
    if arguments is None:
        return None
    return arguments.named_children[0] if arguments.named_children else None


def _elixir_condition(node: Node) -> Node | None:
    if node.type == "binary_operator" and _elixir_guard(node):
        return node.child_by_field_name("right")
    if node.type != "call":
        return None
    target = node.child_by_field_name("target")
    if target is None or target.type != "identifier":
        return None
    return _first_argument(node) if text(target) in {"if", "unless"} else None


def _elixir_target(node: Node) -> str:
    return text(node.child_by_field_name("target")) if node.type == "call" else ""


def _elixir_name(node: Node) -> Node | None:
    head = _first_argument(node)
    if head is not None and head.type == "binary_operator":
        head = head.child_by_field_name("left")
    if head is not None and head.type == "identifier":
        return head
    return head.child_by_field_name("target") if head is not None else None


def _assigned_name(node: Node) -> Node | None:
    parent = node.parent
    if parent is None or parent.type not in {"variable_declarator", "assignment", "variable_declaration"}:
        return None
    return parent.child_by_field_name("name") or parent.child_by_field_name("left")


def _callable_name(node: Node, language: str, is_definition: bool) -> Node | None:
    name = node.child_by_field_name("name")
    if name is None and language == "kotlin":
        name = next((child for child in node.named_children if child.type == "simple_identifier"), None)
    if is_definition:
        name = _elixir_name(node)
    return name if name is not None else _assigned_name(node)


def _callable(node: Node, language: str) -> MutationCallable | None:
    is_definition = language == "elixir" and _elixir_target(node) in {"def", "defp"}
    if node.type not in _CALLABLES[language] and not is_definition:
        return None
    name = _callable_name(node, language, is_definition)
    return MutationCallable(name=text(name) if name is not None else "<anonymous>", span=_span(node), originalText=text(node))


def extract_candidates(source: SourceFile) -> MutationCandidateAnalysis:
    """Extract from exact source bytes; reject invalid encoding or syntax wholesale."""
    analysis = MutationCandidateAnalysis(candidates=[])
    try:
        source.source.decode("utf-8")
    except UnicodeDecodeError:
        return analysis
    if source.language not in _EXPRESSIONS:
        return analysis
    try:
        root = get_parser(source.language).parse(source.source).root_node
    except (LookupError, ValueError):
        return analysis
    if root.has_error:
        return analysis
    _Extraction(source, analysis).run(root)
    analysis.candidates.sort(key=lambda item: (item.span.startByte, item.span.endByte, item.kind, item.id))
    return analysis


def _elixir_pattern(node: Node) -> bool:
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "stab_clause":
        return parent.child_by_field_name("left") == node
    if parent.type == "binary_operator":
        return _elixir_guard(parent) and parent.child_by_field_name("left") == node
    if node.type != "call" or parent.type != "arguments" or parent.parent is None:
        return False
    return _elixir_target(parent.parent) in {"def", "defp"}


def _elixir_excluded(node: Node) -> bool:
    return (
        _elixir_target(node) in {"quote", "defmacro", "defmacrop"}
        or (node.type == "unary_operator" and text(node).startswith("@"))
        or _elixir_pattern(node)
    )


@dataclass
class _Extraction:
    source: SourceFile
    analysis: MutationCandidateAnalysis
    source_hash: str = field(init=False)
    site_types: set[str] = field(init=False)
    seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.source_hash = hashlib.sha256(self.source.source).hexdigest()
        self.site_types = _EXPRESSIONS[self.source.language] | _CONDITIONS[self.source.language]
        if self.source.language == "elixir":
            self.site_types.add("call")

    def candidate(self, site: tuple[MutationKind, Node, Node], owner: MutationCallable | None) -> MutationCandidate:
        kind, token, expression = site
        source = self.source
        span = _span(token)
        identity = json.dumps([self.source_hash, source.path, source.language, kind, span.model_dump()], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return MutationCandidate(
            id=hashlib.sha256(identity.encode("utf-8")).hexdigest(), path=source.path,
            language=source.language, sourceHash=self.source_hash, kind=kind,
            operator=None if kind == "condition" else " ".join(text(token).split()),
            span=span, expressionSpan=_span(expression), originalText=text(token),
            expressionText=text(expression), callable=owner,
        )

    def skip(self, node: Node) -> bool:
        if self.source.language == "elixir" and _elixir_excluded(node):
            return True
        return node.type in _EXCLUDED or "comment" in node.type

    def sites(self, node: Node) -> list[tuple[MutationKind, Node, Node]]:
        condition = _condition(node, self.source.language)
        sites: list[tuple[MutationKind, Node, Node]] = []
        if condition is not None and condition.type not in {"let_condition", "let_chain"}:
            sites.append(("condition", condition, condition))
        sites.extend((kind, token, node) for kind, token in _operators(node, self.source.language))
        return sites

    def record(self, node: Node, owner: MutationCallable | None) -> None:
        for site in self.sites(node):
            candidate = self.candidate(site, owner)
            if candidate.id not in self.seen:
                self.analysis.candidates.append(candidate)
                self.seen.add(candidate.id)

    def visit(self, node: Node, owner: MutationCallable | None) -> list[tuple[Node, MutationCallable | None]]:
        if not node.named_child_count or self.skip(node):
            return []
        owner = _callable(node, self.source.language) or owner
        if node.type in self.site_types:
            self.record(node, owner)
        return [(child, owner) for child in reversed(node.named_children)]

    def run(self, root: Node) -> None:
        pending: list[tuple[Node, MutationCallable | None]] = [(root, None)]
        while pending:
            pending.extend(self.visit(*pending.pop()))
