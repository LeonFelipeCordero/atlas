"""Select declaration nodes from whole application source, never reparse snippets."""

from pathlib import Path

from tree_sitter import Node

from atlas.domain.models import ParsedFile, SourceFile, Symbol
from atlas.metrics.callables import callable_metrics
from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_file
from atlas.parsing.syntax import ParsedSyntax

COFFEE_ROOT = Path(__file__).parent / "fixtures" / "coffee"


def coffee_source(language: str, path: str) -> SourceFile:
    return next(source for source in discover_files(COFFEE_ROOT / language)
                if source.language == language and source.path == path)


def coffee_parsed(language: str, path: str) -> ParsedFile:
    file = parse_file(coffee_source(language, path))
    assert file.parse_error is None
    callable_metrics(file)
    return file


def coffee_symbols(file: ParsedFile, qualified_name: str) -> list[Symbol]:
    symbols = [symbol for symbol in file.symbols
               if symbol.qualified_name == f"{file.source.path}::{qualified_name}"]
    assert symbols, qualified_name
    return symbols


def coffee_node(language: str, path: str, qualified_name: str) -> Node:
    file = coffee_parsed(language, path)
    symbol = coffee_symbols(file, qualified_name)[0]
    root = ParsedSyntax(file.source).tree()
    assert not root.has_error
    node = root.descendant_for_byte_range(symbol.start_byte, symbol.end_byte - 1)
    assert node is not None
    return node
