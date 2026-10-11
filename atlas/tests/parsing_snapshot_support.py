"""Replay parser seams without resolving a graph or depending on native enum pickling."""

import dataclasses
import json
from pathlib import Path
from unittest.mock import patch

from tree_sitter_language_pack import Span, StructureItem

from atlas.domain.models import SourceFile
from atlas.parsing.parser import parse_file
from atlas.parsing.structure import extract_structure
from tests.parsing_fixture import parsing_syntax
from tests.source_snapshot_fixture import assert_case_snapshot, case_bytes, snapshot_value


def manifest(name):
    return json.loads((Path(__file__).parent / "migration" / name).read_text())


def source_variants(module, test, language):
    return [case for case in manifest("parsing_sources.json")
            if case["module"] == module and case["test"] == test and case["language"] == language]


def structure_value(items):
    # Native StructureKind is a Rust enum: asdict/deepcopy cannot pickle it.
    return [
        {
            field.name: str(item.kind).lower() if field.name == "kind"
            else structure_value(item.children) if field.name == "children"
            else snapshot_value(getattr(item, field.name))
            for field in dataclasses.fields(item)
        }
        for item in items
    ]


def native_items(items):
    if items is None:
        return None
    return [StructureItem(**{
        **item,
        "span": Span(**item["span"]) if item["span"] else None,
        "body_span": Span(**item["body_span"]) if item["body_span"] else None,
        "children": native_items(item["children"]),
    }) for item in items]


def source_file(case):
    return SourceFile(case["path"], Path(case["path"]), case["language"],
                      case_bytes(case["family"], case["case_id"], case["path"]))


def parser_value(case):
    return parsed_value(parse_file(source_file(case)))


def assert_parser_snapshot(file, module, test):
    case = next(case for case in manifest('parsing_sources.json')
                if case['module'] == module and case['test'] == test
                and case['language'] == file.source.language
                and case_bytes(case['family'], case['case_id'], case['path']) == file.source.source)
    assert_case_snapshot('parsing', case['snapshot_id'], parsed_value(file))


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


def import_policy_value(case):
    from atlas.metrics.adapters import get_resolution_adapter
    from atlas.metrics.adapters.resolution_paths import import_path, namespace_binding
    source = source_file(case).source.decode()
    path = case.get("import_path", import_path(source))
    return {"source": source, "import_path": import_path(source),
            "adapter_path": get_resolution_adapter(case["language"]).import_path(source),
            "namespace": namespace_binding(source, path)}


def structure_result(case):
    source = source_file(case)
    syntax = parsing_syntax(source.source, source.language)
    native = native_items(case["native"])
    before = structure_value(native) if native is not None else None
    if "missing" in case["test"] and source.language == "csharp":
        with patch("atlas.parsing.structure.get_tags_query", return_value=None):
            from atlas.parsing.structure import _declaration_query
            _declaration_query.cache_clear()
            result = extract_structure(syntax) if native is None else extract_structure(syntax, native)
            _declaration_query.cache_clear()
    else:
        result = extract_structure(syntax) if native is None else extract_structure(syntax, native)
    assert (structure_value(native) if native is not None else None) == before
    return {"native_input": before, "declarations": structure_value(result)}
