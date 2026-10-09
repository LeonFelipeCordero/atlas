"""Elixir metric and resolution policies."""

import re

from dataclasses import replace


from tree_sitter import Node

from .resolution import ResolutionAdapter

from .resolution_paths import quoted_path

from .base import COMMON_METRICS, MetricAdapter

from .parameters import count_parameters

from ...syntax import field, text
from ...language_syntax import DECLARATIONS, _declaration_head

SCOPES = frozenset(
    {
        "def",
        "defp",
        "defmacro",
        "defmacrop",
        "defguard",
        "defguardp",
        "defdelegate",
        "defmodule",
        "defprotocol",
        "defimpl",
    }
)


def target(node: Node) -> str:
    value = field(node, "target") if node.type == "call" else None
    return text(value) if value is not None and value.type == "identifier" else ""


def scope(node: Node) -> bool:
    return target(node) in SCOPES


def call_decision(node: Node) -> bool:
    return target(node) in {"if", "unless"}


def guard_decision(node: Node) -> bool:
    return any(child.type == "when" for child in node.children)


def clause_decision(node: Node) -> bool:
    parent = node.parent
    if parent is None or parent.type == "anonymous_function":
        return False
    pattern = field(node, "left")
    if pattern is None or pattern.type != "arguments":
        return True  # Guarded patterns remain refutable, even guarded wildcards.
    expressions = pattern.named_children
    if len(expressions) != 1:
        return True
    fallback = text(expressions[0]).strip()
    if fallback == "_":
        return False
    return not _cond_fallback(fallback, parent.parent)


def _cond_fallback(fallback: str, owner: Node | None) -> bool:
    return fallback == "true" and owner is not None and target(owner) == "cond"


def arguments(node):
    if node is None:
        return None
    return field(node, "arguments") or next(
        (
            c
            for c in node.named_children
            if c.type in {"arguments", "argument_list", "value_arguments"}
        ),
        None,
    )


def parameter_count(node: Node) -> int | None:
    if node.type == "anonymous_function":
        return _elixir_anonymous_count(node)
    if node.type != "call" or target(node) not in DECLARATIONS:
        return None
    head = _declaration_head(node)
    if head is None or head.has_error:
        return None
    return _elixir_head_count(head)


def _elixir_head_count(head: Node) -> int | None:
    if head.type == "identifier":
        return 0
    return count_parameters(arguments(head)) if head.type == "call" else None


def _elixir_anonymous_count(node: Node) -> int | None:
    clauses = [child for child in node.named_children if child.type == "stab_clause"]
    counts = {_elixir_clause_count(clause) for clause in clauses}
    return counts.pop() if len(counts) == 1 else None


def _elixir_clause_count(clause: Node) -> int | None:
    inputs = field(clause, "left")
    if inputs is None:
        return 0
    if inputs.type == "binary_operator":
        inputs = field(inputs, "left")
    return (
        count_parameters(inputs)
        if inputs is not None and inputs.type == "arguments"
        else None
    )


METRICS = replace(
    COMMON_METRICS,
    decision_overrides={
        "call": call_decision,
        "stab_clause": clause_decision,
        "binary_operator": guard_decision,
    },
    extra_scope=scope,
)


def arity(node) -> int | None:
    args = arguments(node)
    return (
        len(args.named_children)
        if args
        else (0 if node and node.type == "call" else None)
    )


def _clause_signature(node: Node | None) -> tuple[int, int, bool]:
    if node is None:
        return 0, 0, False
    args = arguments(node)
    head = args.named_children[0] if args and args.named_children else None
    if head and head.type == "binary_operator":
        head = field(head, "left")
    parameters = arguments(head)
    count, defaults = _parameter_counts(parameters)
    return count - defaults, count, text(field(node, "target")) == "defp"


def _parameter_counts(parameters: Node | None) -> tuple[int, int]:
    if parameters is None:
        return 0, 0
    return len(parameters.named_children), sum(
        "\\\\" in text(c) for c in parameters.named_children
    )


def _resolution_pipeline(node: Node | None) -> bool:
    if node is None or node.parent is None:
        return False
    parent = node.parent
    return (
        parent.type == "binary_operator"
        and field(parent, "right") == node
        and "|>" in text(parent)
    )


def _pipeline_identifier(node: Node | None, pipeline: bool) -> bool:
    return node is not None and node.type == "identifier" and pipeline


def _call_arity(node: Node | None) -> int | None:
    count = arity(node)
    pipeline = _resolution_pipeline(node)
    if count is None and _pipeline_identifier(node, pipeline):
        count = 0
    if count is None:
        return None
    return count + 1 if pipeline else count


def _clause_matches(symbol, clauses, count, call) -> bool:
    clause = clauses.get(symbol.key)
    if clause is None:
        return False
    minimum, maximum, private = clause
    if not minimum <= count <= maximum:
        return False
    return not private or (not call.qualifier and symbol.file_path == call.file_path)


class ElixirResolution(ResolutionAdapter):
    def import_path(self, source: str) -> str:
        match = re.search(r"\b(?:import|alias|require|use)\s+([\w.:/]+)", source)
        return quoted_path(source) or (match[1] if match else source.strip())

    family = "elixir"
    member_nodes = {"dot": (("left",), ("right",))}
    receiver_names = {"alias"}

    def is_import_node(self, node):
        return node.type == "call" and text(field(node, "target")) in {
            "alias",
            "import",
        }

    def module_identity(self, file, symbol, syntax):
        return (
            symbol.name
            if symbol.kind == "module"
            else symbol.qualified_name.split("::")[-1]
        )

    def import_key(self, ctx, file, source, position):
        targets = ctx.modules.declared(file, self.import_path(source))
        return targets[0].key if len(targets) == 1 else None

    def import_item(self, ctx, file, source, path, position):
        alias = re.search(r"\bas\s*:?\s*([\w]+)", source)
        return [
            (
                alias[1] if alias else path.rsplit(".", 1)[-1],
                ctx.modules.declared(file, path),
                False,
            )
        ]

    def qualified(self, resolver, file, qualifier, name, call):
        return resolver.members(resolver.modules.declared(file, qualifier), name, True)

    def clauses(self, repository, syntax):
        clauses = {}
        for symbol in repository.symbols:
            if symbol.language != self.family or symbol.kind not in {
                "function",
                "method",
            }:
                continue
            node = syntax[symbol.file_path].node(symbol.start_byte, symbol.end_byte)
            clauses[symbol.key] = _clause_signature(node)
        return clauses

    def select(self, identity, file, call, matches):
        node = identity.syntax[file.source.path].node(call.start_byte, call.end_byte)
        count = _call_arity(node)
        if count is None:
            return matches if len(matches) == 1 else []
        clauses = identity.clauses
        matches = [s for s in matches if _clause_matches(s, clauses, count, call)]
        identities = {(s.parent_key, s.name) for s in matches}
        return matches if len(identities) == 1 else []


ADAPTER = MetricAdapter(metrics=METRICS, parameter_count=parameter_count)
