"""Small tree and domain records for resolution unit tests; no parser required."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from atlas.domain.models import Call, ParsedFile, SourceFile, Symbol


def node(kind: str = "identifier", value: str = "", **fields: Any) -> Any:
    start, end = fields.pop("start", 0), fields.pop("end", 100)
    children = fields.pop("children", None)
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


def symbol(key: str = "target", name: str = "run", **overrides: Any) -> Symbol:
    return Symbol(key, "a.py", "python", name, name, overrides.get("kind", "function"),
                  overrides.get("parent", "file:a.py"), overrides.get("start", 0), overrides.get("end", 100),
                  1, 1, 2, 1, None, None, [])


def call(name: str = "run", start: int = 20, end: int = 25) -> Call:
    return Call("a.py", name, start, end, 3, "run()", True)
