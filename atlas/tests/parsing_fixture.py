"""Construct parsing context for small in-memory test sources."""

from pathlib import Path

from tree_sitter import Node

from atlas.parsing.discovery import SourceFile
from atlas.parsing.syntax import ParsedSyntax


def parsing_syntax(source: str | bytes, language: str, root: Node | None = None) -> ParsedSyntax:
    content = source.encode() if isinstance(source, str) else source
    return ParsedSyntax(SourceFile("sample", Path("sample"), language, content), root)
