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
from atlas.domain.mutation_candidates import (
    MutationCallable,
    MutationCandidate,
    MutationCandidateAnalysis,
    MutationCandidateDiagnostic,
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
    "php": {"binary_expression", "unary_op_expression", "augmented_assignment_expression"},
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
    "php": {"if_statement", "else_if_clause", "while_statement", "do_statement", "for_statement", "conditional_expression"},
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
    "php": {"function_definition", "method_declaration", "anonymous_function", "arrow_function"},
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
_COMPARISONS = {"==", "!=", "===", "!==", "<", "<=", ">", ">=", "in", "not in", "is", "is not", "instanceof", "!in", "!is", "<>", "=~", "<=>"}
_LOGICAL = {"and", "or", "not", "&&", "||", "!", "??", "andalso", "orelse", "xor"}
_ARITHMETIC = {"+", "-", "*", "/", "//", "%", "**"}
_ASSIGNMENT = {"+=", "-=", "*=", "/=", "//=", "%=", "**=", "&&=", "||=", "??="}
_UNSUPPORTED = {"switch_statement", "switch_expression", "match_statement", "match_expression", "when_expression", "macro_invocation", "stab_clause"}


def _text(node: Node, data: bytes) -> str:
    return data[node.start_byte:node.end_byte].decode("utf-8")


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


def _operator_tokens(node: Node, source: SourceFile) -> list[Node]:
    if node.type not in _EXPRESSIONS[source.language]:
        return []
    # Named tokens (Python's `is not`, Kotlin's assignment operator) may
    # themselves contain tokens. Select only direct operator children.
    return [child for i, child in enumerate(node.children) if (
        node.field_name_for_child(i) in {"operator", "operators"}
        or not child.is_named
        or child.type in {"assignment_operator"}
    )]


def _operator_kind(operator: str, language: str, expression_type: str) -> MutationKind | None:
    # Elixir <> concatenates binaries; PHP <> compares for inequality.
    if operator == "<>" and language != "php":
        return None
    if operator == "*" and language in {"rust", "go"} and expression_type == "unary_expression":
        return None  # Pointer dereference is not arithmetic multiplication.
    return _kind(operator)


def _operators(node: Node, source: SourceFile, analysis: MutationCandidateAnalysis) -> list[tuple[MutationKind, Node]]:
    result: list[tuple[MutationKind, Node]] = []
    for token in _operator_tokens(node, source):
        operator = " ".join(_text(token, source.source).split())
        kind = _operator_kind(operator, source.language, node.type)
        if kind is not None:
            result.append((kind, token))
        elif operator not in {"=", "when", "(", ")", ","}:
            analysis.diagnostics.append(_diagnostic(source, ("unsupported-operator", f"Operator {operator!r} has no mutation mapping for {source.language}."), token))
    return result


def _condition(node: Node, source: SourceFile) -> Node | None:
    language = source.language
    if language == "elixir":
        return _elixir_condition(node, source.source)
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


def _elixir_guard(node: Node, data: bytes) -> bool:
    operator = node.child_by_field_name("operator")
    return operator is not None and _text(operator, data) == "when"


def _first_argument(node: Node) -> Node | None:
    arguments = next((child for child in node.named_children if child.type == "arguments"), None)
    if arguments is None:
        return None
    return arguments.named_children[0] if arguments.named_children else None


def _elixir_condition(node: Node, data: bytes) -> Node | None:
    if node.type == "binary_operator" and _elixir_guard(node, data):
        return node.child_by_field_name("right")
    if node.type != "call":
        return None
    target = node.child_by_field_name("target")
    if target is None or target.type != "identifier":
        return None
    return _first_argument(node) if _text(target, data) in {"if", "unless"} else None


def _elixir_target(node: Node, source: SourceFile) -> str:
    target = node.child_by_field_name("target")
    return _text(target, source.source) if node.type == "call" and target is not None else ""


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


def _callable_name(node: Node, source: SourceFile, is_definition: bool) -> Node | None:
    name = node.child_by_field_name("name")
    if name is None and source.language == "kotlin":
        name = next((child for child in node.named_children if child.type == "simple_identifier"), None)
    if is_definition:
        name = _elixir_name(node)
    return name if name is not None else _assigned_name(node)


def _callable(node: Node, source: SourceFile) -> MutationCallable | None:
    is_definition = source.language == "elixir" and _elixir_target(node, source) in {"def", "defp"}
    if node.type not in _CALLABLES[source.language] and not is_definition:
        return None
    name = _callable_name(node, source, is_definition)
    return MutationCallable(name=_text(name, source.source) if name is not None else "<anonymous>", span=_span(node), originalText=_text(node, source.source))


def _diagnostic(source: SourceFile, detail: tuple[str, str], node: Node | None = None) -> MutationCandidateDiagnostic:
    code, message = detail
    return MutationCandidateDiagnostic(path=source.path, language=source.language, code=code, message=message, span=_span(node) if node is not None else None)


def extract_candidates(source: SourceFile) -> MutationCandidateAnalysis:
    """Extract from exact source bytes; reject invalid encoding or syntax wholesale."""
    analysis = MutationCandidateAnalysis(candidates=[], diagnostics=[])
    try:
        source.source.decode("utf-8")
    except UnicodeDecodeError:
        analysis.diagnostics.append(_diagnostic(source, ("invalid-utf8", "Source is not valid UTF-8; extraction skipped.")))
        return analysis
    if source.language not in _EXPRESSIONS:
        analysis.diagnostics.append(_diagnostic(source, ("unsupported-language", "No mutation adapter for this language.")))
        return analysis
    try:
        root = get_parser(source.language).parse(source.source).root_node
    except (LookupError, ValueError) as error:
        analysis.diagnostics.append(_diagnostic(source, ("parser-unavailable", str(error))))
        return analysis
    if root.has_error:
        analysis.diagnostics.append(_diagnostic(source, ("syntax-error", "Parse contains errors or missing tokens; extraction skipped."), root))
        return analysis
    _extract_tree(root, source, analysis)
    analysis.candidates.sort(key=lambda item: (item.span.startByte, item.span.endByte, item.kind, item.id))
    analysis.diagnostics.sort(key=lambda item: (item.span.startByte if item.span else -1, item.code))
    return analysis


def _elixir_pattern(node: Node, source: SourceFile) -> bool:
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "stab_clause":
        return parent.child_by_field_name("left") == node
    if parent.type == "binary_operator":
        return _elixir_guard(parent, source.source) and parent.child_by_field_name("left") == node
    if node.type != "call" or parent.type != "arguments" or parent.parent is None:
        return False
    return _elixir_target(parent.parent, source) in {"def", "defp"}


def _elixir_excluded(node: Node, source: SourceFile) -> str | None:
    if source.language != "elixir":
        return None
    if _elixir_target(node, source) in {"quote", "defmacro", "defmacrop"}:
        return "Elixir quoted AST and macro definitions are not runtime expression syntax; extraction skipped."
    if node.type == "unary_operator" and _text(node, source.source).startswith("@"):
        return "Elixir module attribute/type syntax is not analyzed for runtime mutations."
    return None


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
            operator=None if kind == "condition" else " ".join(_text(token, source.source).split()),
            span=span, expressionSpan=_span(expression), originalText=_text(token, source.source),
            expressionText=_text(expression, source.source), callable=owner,
        )

    def skip(self, node: Node) -> bool:
        if self.source.language == "elixir" and _elixir_pattern(node, self.source):
            return True
        excluded = _elixir_excluded(node, self.source)
        if excluded is not None:
            self.analysis.diagnostics.append(_diagnostic(self.source, ("unsupported-construct", excluded), node))
            return True
        if node.type in {"let_condition", "let_chain"}:
            self.analysis.diagnostics.append(_diagnostic(self.source, ("unsupported-condition", "Rust let conditions/chains are pattern bindings, not boolean mutation sites."), node))
        return node.type in _EXCLUDED or "comment" in node.type

    def sites(self, node: Node) -> list[tuple[MutationKind, Node, Node]]:
        condition = _condition(node, self.source)
        sites: list[tuple[MutationKind, Node, Node]] = []
        if condition is not None and condition.type not in {"let_condition", "let_chain"}:
            sites.append(("condition", condition, condition))
        sites.extend((kind, token, node) for kind, token in _operators(node, self.source, self.analysis))
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
        owner = _callable(node, self.source) or owner
        if node.type in _UNSUPPORTED:
            self.analysis.diagnostics.append(_diagnostic(self.source, ("unsupported-construct", f"{node.type} is not modeled as a boolean condition."), node))
        if node.type in self.site_types:
            self.record(node, owner)
        return [(child, owner) for child in reversed(node.named_children)]


def _extract_tree(root: Node, source: SourceFile, analysis: MutationCandidateAnalysis) -> None:
    extraction = _Extraction(source, analysis)
    pending: list[tuple[Node, MutationCallable | None]] = [(root, None)]
    while pending:
        node, owner = pending.pop()
        pending.extend(extraction.visit(node, owner))
