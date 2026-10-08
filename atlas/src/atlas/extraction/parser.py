"""Parse in-memory source files into graph records and repository-wide views.

Use ``parse_file`` for one source or ``parse_files`` for an ordered batch;
``file_key`` supplies file-node identifiers. Lines and columns are one-based,
byte offsets are zero-based, and stored end offsets are exclusive.
"""

import hashlib
from functools import cache


from tree_sitter_language_pack import ProcessConfig, StructureItem, get_language, get_parser, process

from ..adapters import get_adapter
from .complexity import calculate_complexity
from ..discovery import SourceFile
from .structure import extract_structure
from .syntax import FALLBACK_CALL_TYPES, call_sites


from ..domain.models import (
    Symbol,
    Import,
    Call,
    Inheritance,
    ParsedFile,
    ParsedRepository,
    file_key,
)


@cache
def _has_call_nodes(language: str) -> bool:
    grammar = get_language(language)
    return any(
        grammar.node_kind_for_id(index) in FALLBACK_CALL_TYPES
        for index in range(grammar.node_kind_count)
    )


def _extract_calls(file: SourceFile) -> list[Call]:
    adapter = get_adapter(file.language)
    # Data/markup grammars cannot produce fallback calls; avoid parsing them twice.
    if adapter.call_sites is call_sites and not _has_call_nodes(file.language):
        return []
    root = get_parser(file.language).parse(file.source).root_node
    calls = []
    for site in adapter.call_sites(root):
        node, offset, _, _ = site
        name, bare_target, qualifier = adapter.normalize_call(site)
        if not name:
            continue
        start, end = node.start_byte + offset, node.end_byte + offset
        calls.append(
            Call(
                file.path,
                name,
                start,
                end,
                file.source.count(b"\n", 0, start) + 1,
                file.source[start:end].decode("utf-8", errors="replace")[:300],
                bare_target,
                qualifier,
                adapter.call_relationship(site),
            )
        )
    return calls


def _add_structure(
    file: ParsedFile, item: StructureItem, parent_key: str, ancestors: list[str]
) -> None:
    span = item.span
    if span is None:
        return
    name = item.name or "<anonymous>"
    qualified_name = f"{file.source.path}::{'.'.join([*ancestors, name])}"
    key = f"symbol:{qualified_name}:{span.start_byte}"
    kind = str(item.kind).lower()
    symbol = Symbol(
        key,
        file.source.path,
        file.source.language,
        name,
        qualified_name,
        kind,
        parent_key,
        span.start_byte,
        span.end_byte,
        span.start_line + 1,
        span.start_column + 1,
        span.end_line + 1,
        span.end_column + 1,
        item.signature,
        item.visibility,
        list(item.decorators),
    )
    file.symbols.append(symbol)
    for target_name in get_adapter(file.source.language).inheritance(
        file.source.language, kind, item.signature or ""
    ):
        file.inheritances.append(
            Inheritance(
                key,
                file.source.path,
                file.source.language,
                target_name,
                symbol.start_line,
                item.signature or "",
            )
        )
    for child in item.children:
        _add_structure(file, child, key, [*ancestors, name])


def parse_file(source: SourceFile) -> ParsedFile:
    """Parse in-memory bytes into graph records; no filesystem reads occur.

    Call extraction runs first. Parser failures are recorded in ``parse_error``;
    native processing failures return early, retaining the digest and any calls.
    Text decoding replaces invalid UTF-8; syntax errors need not raise.

    Args:
        source: File path, language identifier, and source bytes to index.
    Returns:
        Parsed records with a SHA-256 digest; callables get complexity and size metrics.
    Raises:
        ValueError: The language is unsupported (including C and C++).
        Exception: Uncaught structure extraction, record validation, or complexity
            parsing failures. Call-parser and native processing errors are caught.
    Examples:
        >>> from pathlib import Path
        >>> source = SourceFile("main.py", Path("main.py"), "python", b"run()")
        >>> parsed = parse_file(source)
        >>> parsed.source.path
        'main.py'
        >>> digest = parse_file(source).content_hash  # Stable for identical bytes.
    """
    adapter = get_adapter(source.language)
    parsed = ParsedFile(source, hashlib.sha256(source.source).hexdigest(), None)
    text = source.source.decode("utf-8", errors="replace")
    syntax_source = text.encode("utf-8")
    syntax_file = SourceFile(
        source.path, source.absolute_path, source.language, syntax_source
    )
    try:
        parsed.calls = _extract_calls(syntax_file)
    except Exception as exception:
        parsed.parse_error = f"Call extraction failed: {exception}"
    try:
        result = process(text, ProcessConfig(language=source.language))
    except Exception as exception:
        parsed.parse_error = str(exception)
        return parsed
    native_imports = [
        (item.source, item.span.start_line + 1)
        for item in result.imports
        if item.span is not None
    ]
    parsed.imports = [
        Import(source.path, value, line)
        for value, line in adapter.imports(syntax_file, native_imports)
    ]
    structure = extract_structure(syntax_source, source.language, result.structure)
    for item in structure:
        _add_structure(parsed, item, file_key(source.path), [])
    _add_callable_metrics(parsed, syntax_source)
    return parsed


def _add_callable_metrics(file: ParsedFile, syntax_source: bytes) -> None:
    callables = [
        symbol for symbol in file.symbols if symbol.kind in {"function", "method"}
    ]
    if not callables:
        return
    root = get_parser(file.source.language).parse(syntax_source).root_node
    adapter = get_adapter(file.source.language)
    for symbol in callables:
        symbol.line_count = max(
            0, symbol.end_line - symbol.start_line + int(symbol.end_column > 1)
        )
        node = root.descendant_for_byte_range(symbol.start_byte, symbol.end_byte - 1)
        if node is not None:
            symbol.complexity = calculate_complexity(node, adapter.metrics)
            symbol.parameter_count = adapter.parameter_count(node)


def parse_files(files: list[SourceFile]) -> ParsedRepository:
    """Parse an ordered batch sequentially, without deduplication or resolution.

    Args:
        files: In-memory sources to parse, in the desired repository order.
    Returns:
        A repository containing one ParsedFile per input, preserving order.
    Raises:
        Exception: Uncaught failures from ``parse_file`` or repository validation;
            no partial repository is returned when parsing raises.
    Examples:
        >>> parse_files([]).files
        []
        >>> from pathlib import Path
        >>> source = SourceFile("main.py", Path("main.py"), "python", b"run()")
        >>> repository = parse_files([source])
        >>> repository.files[0].source.path
        'main.py'
    """
    return ParsedRepository([parse_file(file) for file in files])
