"""Lossless records for complete-project parsing and native-structure snapshots."""

import dataclasses

from tests.source_snapshot_fixture import snapshot_value


def parsed_value(file):
    return {
        "source": {"path": file.source.path, "language": file.source.language,
                   "bytes": file.source.source},
        "content_hash": file.content_hash,
        "parse_error": file.parse_error,
        "declarations": file.symbols,
        "calls": file.calls,
        "imports": file.imports,
        "inheritances": file.inheritances,
    }


def structure_value(items):
    # StructureKind is a native enum that cannot be deep-copied with asdict.
    return [
        {
            field.name: str(item.kind).lower() if field.name == "kind"
            else structure_value(item.children) if field.name == "children"
            else snapshot_value(getattr(item, field.name))
            for field in dataclasses.fields(item)
        }
        for item in items
    ]
