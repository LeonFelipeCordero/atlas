"""Small overridable records and syntax stubs; no parser is started."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from atlas.domain.models import Call, ParsedFile, SourceFile, Symbol, file_key
from atlas.metrics.resolution_contract import ResolutionRequest


class SyntaxNode:
    """Keep tree node identity, including when nodes are dictionary keys."""

    def __init__(self, **values):
        self.__dict__.update(values)


def node(
    kind: str = "identifier",
    value: str = "",
    *,
    children=(),
    named=None,
    start: int = 0,
    end: int = 100,
    error: bool = False,
    **fields,
) -> Any:
    entries = list(children)
    for entry in fields.values():
        for child in entry if isinstance(entry, list) else [entry]:
            if child is not None and child not in entries:
                entries.append(child)
    result: Any = SyntaxNode(
        type=kind,
        text=value.encode(),
        children=entries,
        named_children=list(entries if named is None else named),
        start_byte=start,
        end_byte=end,
        has_error=error,
        parent=None,
        prev_named_sibling=None,
    )
    result.child_by_field_name = lambda name: fields.get(name)
    result.children_by_field_name = lambda name: (
        (fields[name] if isinstance(fields.get(name), list) else [fields[name]])
        if name in fields
        else []
    )
    for child in entries:
        child.parent = result
    return result


def parsed(
    path: str = "src/main.py", language: str = "python", *, symbols=(), **overrides
) -> ParsedFile:
    return ParsedFile(
        SourceFile(path, Path("/adapter-project") / path, language, b" " * 200),
        "digest",
        None,
        symbols=list(symbols),
        **overrides,
    )


def symbol(
    name: str = "run",
    *,
    path: str = "src/main.py",
    language: str = "python",
    start: int = 10,
    end: int = 20,
    kind: str = "function",
    parent: str | None = None,
    **overrides,
) -> Symbol:
    values: dict[str, Any] = dict(
        key=f"{path}:{name}:{start}",
        file_path=path,
        language=language,
        name=name,
        qualified_name=name,
        kind=kind,
        parent_key=parent or file_key(path),
        start_byte=start,
        end_byte=end,
        start_line=1,
        start_column=1,
        end_line=1,
        end_column=2,
        signature=None,
        visibility=None,
        decorators=[],
    )
    values.update(overrides)
    return Symbol(**values)


def request(
    file: ParsedFile | None = None,
    *,
    name: str = "run",
    qualifier: str | None = None,
    start: int = 50,
    end: int = 60,
) -> ResolutionRequest:
    file = file or parsed()
    return ResolutionRequest(
        file,
        Call(file.source.path, name, start, end, 1, "", qualifier=qualifier),
        None,
        name,
        qualifier,
    )


def syntax(*, nodes=(), declarations=None, adapter=None, file=None, **overrides) -> Any:
    spans = declarations or {}
    values = dict(
        nodes=list(nodes),
        node=lambda start, end: spans.get((start, end)),
        adapter=adapter,
        file=file or parsed(),
        imports=[],
        bindings=[],
        static=lambda symbol: False,
        shadowed=lambda name, position: False,
        member_rebound=lambda name, member: False,
        class_rebound=lambda parent, name: False,
        _visible=lambda scope, position: True,
        receiver_scope_cache={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)
