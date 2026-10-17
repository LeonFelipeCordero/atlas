"""Small source records and syntax doubles for metric unit tests."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tree_sitter import Node

from atlas.domain.models import ParsedFile, SourceFile, Symbol


def symbol(**overrides) -> Symbol:
    return Symbol(**{
        "key": "fn", "file_path": "src/a.py", "language": "python",
        "name": "brew", "qualified_name": "a.brew", "kind": "function",
        "parent_key": "file:src/a.py", "start_byte": 2, "end_byte": 12,
        "start_line": 2, "start_column": 1, "end_line": 5, "end_column": 1,
        "signature": "brew()", "visibility": "public", "decorators": [],
        **overrides,
    })


def parsed_file(path: str = "src/a.py", source: bytes = b"pass\n", **overrides) -> ParsedFile:
    return ParsedFile(**{
        "source": SourceFile(path, Path("/repo") / path, "python", source),
        "content_hash": "digest", "parse_error": None, **overrides,
    })


@dataclass(eq=False)
class SyntaxNode:
    type: str
    named_children: list["SyntaxNode"] = field(default_factory=list)
    children: list["SyntaxNode"] = field(default_factory=list)
    parent: "SyntaxNode | None" = None
    body: "SyntaxNode | None" = None

    def child_by_field_name(self, name: str) -> "SyntaxNode | None":
        return self.body if name == "body" else None


def syntax(kind: str, *children: SyntaxNode) -> SyntaxNode:
    return SyntaxNode(kind, list(children))


def as_node(node: SyntaxNode) -> Node:
    return cast(Node, node)


def graph_node(key: str, level: str, parent: str | None = None, **overrides) -> dict[str, object]:
    return {"stableKey": key, "type": level, "kind": level, "level": level,
            "parentStableKey": parent, **overrides}


def edge(source: str, target: str, kind: str = "IMPORTS", **overrides) -> dict[str, object]:
    return {"sourceStableKey": source, "targetStableKey": target, "type": kind,
            "confidence": "EXTRACTED", **overrides}
