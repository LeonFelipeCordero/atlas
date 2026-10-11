"""Focused adapter outputs that complete graph records alone cannot expose."""

from typing import Any

from tree_sitter_language_pack import get_parser

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.elixir import _call_arity, _clause_signature
from atlas.metrics.adapters.javascript import export_bindings
from atlas.metrics.adapters.python import irrefutable_pattern
from atlas.metrics.resolution_syntax import Syntax, names
from atlas.parsing.adapters.javascript import unparenthesized
from atlas.syntax import walk


def adapter_records(case_id: str, repo: ParsedRepository) -> dict[str, Any]:
    file = repo.files[0]
    root = get_parser(file.source.language).parse(file.source.source).root_node
    if case_id.startswith("python-irrefutable-patterns-"):
        pattern = next(node for node in walk(root) if node.type == "case_pattern")
        return {"irrefutable": irrefutable_pattern(pattern)}
    if case_id.startswith("parentheses-only-unwrap-single-expressions-"):
        expression = root.named_children[0].named_children[0]
        return {"unparenthesized_type": unparenthesized(expression).type}
    if case_id.startswith(
        "recursive-binding-names-still-ignore-types-and-member-targets-"
    ):
        pattern = next(
            (node for node in walk(root) if node.type == "object_pattern"), None
        )
        target = (
            pattern if pattern is not None else root.named_children[0].named_children[0]
        )
        return {"binding_names": names(target)}
    if case_id.startswith("elixir-default-guard-and-pipeline-arities-"):
        calls = {node.text: node for node in walk(root) if node.type == "call"}
        finish = next(node for node in walk(root) if node.text == b"finish")
        return {
            "clause_signature": _clause_signature(root.named_children[0]),
            "next_arity": _call_arity(calls[b"next(extra)"]),
            "finish_arity": _call_arity(finish),
            "absent_clause_signature": _clause_signature(None),
            "absent_call_arity": _call_arity(None),
        }
    if case_id.startswith("js-export-deduplication-preserves-alias-keys-and-order-"):
        exports = export_bindings(
            file, Syntax(file, get_resolution_adapter(file.source.language))
        )
        return {"export_order": list(exports), "exports": exports}
    if case_id.startswith("import-directives-on-one-line-keep-exact-source-selection-"):
        syntax = Syntax(file, get_resolution_adapter(file.source.language))
        selected = syntax.import_node(1, "import {b} from './b'")
        return {
            "ambiguous_line": syntax.import_node(1),
            "selected": None
            if selected is None
            else {
                "type": selected.type,
                "text": selected.text,
                "start_byte": selected.start_byte,
                "end_byte": selected.end_byte,
            },
        }
    return {}
