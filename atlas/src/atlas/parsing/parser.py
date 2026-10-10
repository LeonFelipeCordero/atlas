"""Parse in-memory source files into graph records and repository-wide views.

Use ``parse_file`` for one source or ``parse_files`` for an ordered batch;
``file_key`` supplies file-node identifiers. Lines and columns are one-based,
byte offsets are zero-based, and stored end offsets are exclusive.
"""

import hashlib
from functools import cache


from tree_sitter import Node
from tree_sitter_language_pack import ProcessConfig, StructureItem, get_language, get_parser, process

from .adapters import DEFAULT_ADAPTER, LanguageAdapter, get_adapter
from ..domain.models import SourceFile
from .structure import _declaration_query, extract_structure
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


def _parse_syntax(file: SourceFile, adapter: LanguageAdapter) -> Node | None:
    if (
        adapter.call_sites is not call_sites
        or _has_call_nodes(file.language)
        or adapter.import_node is not None
        or _declaration_query(file.language) is not None
    ):
        return get_parser(file.language).parse(file.source).root_node
    return None


def _syntax_error(root: Node | None) -> str | None:
    if root is None or not root.has_error:
        return None
    pending = [root]
    while pending:
        node = pending.pop()
        if node.is_error or node.is_missing:
            line, column = node.start_point
            return f"Syntax error at line {line + 1}, column {column + 1}; analysis may be incomplete."
        pending.extend(reversed(node.children))
    return None


def _extract_calls(
    file: SourceFile, *, root: Node | None = None, adapter: LanguageAdapter | None = None
) -> list[Call]:
    adapter = adapter or get_adapter(file.language)
    # Data/markup grammars cannot produce fallback calls; avoid parsing them twice.
    if adapter.call_sites is call_sites and not _has_call_nodes(file.language):
        return []
    # Standalone tests omit the root; parse_file supplies the shared tree.
    if root is None:
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

    Calls, imports, and structure share a syntax tree when needed.
    Native processing runs separately. Parser failures propagate to the caller.
    Text decoding replaces invalid UTF-8; syntax errors are recorded as diagnostics.

    Args:
        source: File path, language identifier, and source bytes to index.
    Returns:
        Parsed records with a SHA-256 digest; callable metrics remain unset.
    Raises:
        ValueError: The language is unsupported (including C and C++).
        Exception: Call extraction, native processing, structure extraction,
            or record validation failures.
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
    root = _parse_syntax(syntax_file, adapter)
    # Generic grammars may reject valid dialects (e.g. Tailwind CSS). Dedicated
    # code adapters report concrete ERROR/missing nodes, not grammar-only flags.
    parsed.parse_error = _syntax_error(root) if adapter is not DEFAULT_ADAPTER else None
    parsed.calls = _extract_calls(syntax_file, root=root, adapter=adapter)
    result = process(text, ProcessConfig(language=source.language))
    native_imports = [
        (item.source, item.span.start_line + 1)
        for item in result.imports
        if item.span is not None
    ]
    parsed.imports = [
        Import(source.path, value, line)
        for value, line in adapter.imports(syntax_file, native_imports, root=root)
    ]
    structure = extract_structure(
        syntax_source, source.language, result.structure, root=root
    )
    for item in structure:
        _add_structure(parsed, item, file_key(source.path), [])
    return parsed


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
