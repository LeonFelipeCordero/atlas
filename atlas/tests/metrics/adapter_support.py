"""Small overridable records and syntax stubs; no parser is started."""

from itertools import chain
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

from typing_extensions import Unpack

from atlas.domain.models import Call, ParsedFile, SourceFile, Symbol, file_key
from atlas.metrics.resolution_contract import ResolutionRequest


class SyntaxNode:
    """Keep tree node identity, including when nodes are dictionary keys."""

    def __init__(self, **values):
        self.__dict__.update(values)


def node(
    kind: str = "identifier",
    value: str = "",
    **fields: Any,
) -> Any:
    entries = list(fields.pop("children", ()))
    named = fields.pop("named", None)
    start = fields.pop("start", 0)
    end = fields.pop("end", 100)
    error = fields.pop("error", False)
    field_children = chain.from_iterable(
        entry if isinstance(entry, list) else [entry] for entry in fields.values()
    )
    for child in field_children:
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
    path: str = "src/main.py", language: str = "python", **overrides: Any
) -> ParsedFile:
    return ParsedFile(
        SourceFile(path, Path("/adapter-project") / path, language, b" " * 200),
        "digest",
        None,
        symbols=list(overrides.pop("symbols", ())),
        **overrides,
    )


def symbol(
    name: str = "run",
    **overrides: Any,
) -> Symbol:
    path = overrides.pop("path", "src/main.py")
    start = overrides.pop("start", 10)
    parent = overrides.pop("parent", None)
    values: dict[str, Any] = dict(
        key=f"{path}:{name}:{start}",
        file_path=path,
        language="python",
        name=name,
        qualified_name=name,
        kind="function",
        parent_key=parent or file_key(path),
        start_byte=start,
        end_byte=overrides.pop("end", 20),
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


class RequestOptions(TypedDict, total=False):
    name: str
    qualifier: str | None
    start: int
    end: int


def request(
    file: ParsedFile | None = None, **options: Unpack[RequestOptions]
) -> ResolutionRequest:
    file = file or parsed()
    name = options.get("name", "run")
    qualifier = options.get("qualifier")
    start = options.get("start", 50)
    end = options.get("end", 60)
    return ResolutionRequest(
        file,
        Call(file.source.path, name, start, end, 1, "", qualifier=qualifier),
        None,
        name,
        qualifier,
    )


def syntax(**overrides: Any) -> Any:
    spans = overrides.pop("declarations", None) or {}
    values = dict(
        nodes=list(overrides.pop("nodes", ())),
        node=lambda start, end: spans.get((start, end)),
        adapter=overrides.pop("adapter", None),
        file=overrides.pop("file", None) or parsed(),
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
