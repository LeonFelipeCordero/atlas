"""Enrich extracted callable records using language-specific metric policies."""

from tree_sitter_language_pack import get_parser

from ..domain.models import ParsedFile, ParsedRepository
from .adapters import get_metric_adapter
from .complexity import calculate_complexity


def callable_metrics(file: ParsedFile) -> None:
    """Populate callable metrics from retained source, without filesystem reads.

    Syntax offsets use the same replacement-decoded UTF-8 as extraction.
    """
    callables = [
        symbol for symbol in file.symbols if symbol.kind in {"function", "method"}
    ]
    if not callables:
        return
    syntax_source = file.source.source.decode("utf-8", errors="replace").encode("utf-8")
    root = get_parser(file.source.language).parse(syntax_source).root_node
    adapter = get_metric_adapter(file.source.language)
    for symbol in callables:
        symbol.line_count = max(
            0, symbol.end_line - symbol.start_line + int(symbol.end_column > 1)
        )
        node = root.descendant_for_byte_range(symbol.start_byte, symbol.end_byte - 1)
        if node is not None:
            symbol.complexity = calculate_complexity(node, adapter.metrics)
            symbol.parameter_count = adapter.parameter_count(node)


def add_callable_metrics(repository: ParsedRepository) -> None:
    """Enrich each parsed file's callable records before graph construction."""
    for file in repository.files:
        callable_metrics(file)
