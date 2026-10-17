"""Small tree and domain records for resolution unit tests; no parser required."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from atlas.domain.models import Call, ParsedFile, SourceFile, Symbol


def node(kind: str = "identifier", value: str = "", start: int = 0, end: int = 100,
         children: list[Any] | None = None, **fields: Any) -> Any:
    children = children if children is not None else list(fields.values())
    result = SimpleNamespace(type=kind, text=value.encode(), start_byte=start, end_byte=end,
                             parent=None, children=children, named_children=children,
                             start_point=SimpleNamespace(row=0))
    result.child_by_field_name = fields.get
    result.children_by_field_name = lambda name: [fields[name]] if name in fields else []
    for child in children:
        child.parent = result
    return result


def parsed_file(symbols: list[Symbol] | None = None) -> ParsedFile:
    return ParsedFile(SourceFile("a.py", Path("/unit/a.py"), "python", b"source"),
                      "digest", None, symbols or [])


def symbol(key: str = "target", name: str = "run", kind: str = "function",
           parent: str = "file:a.py", start: int = 0, end: int = 100) -> Symbol:
    return Symbol(key, "a.py", "python", name, name, kind, parent, start, end,
                  1, 1, 2, 1, None, None, [])


def call(name: str = "run", start: int = 20, end: int = 25) -> Call:
    return Call("a.py", name, start, end, 3, "run()", True)
