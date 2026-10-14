"""Cold whole-repository budget and whole-project unnecessary-work guards."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter_language_pack import get_parser

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.resolution import ImportBindings, Modules
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolution_syntax import Syntax
from atlas.parsing.discovery import SourceFile
from atlas.parsing.parser import _extract_calls, parse_files
from tests.coffee_fixture import coffee_sources
from tests.import_project_support import project_sources

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_BUDGET_SECONDS = 15


def test_analyzes_this_repository_within_fast_cold_process_budget():
    script = """
import json, sys
from pathlib import Path
from atlas.indexer import analyze_repository
artifact = analyze_repository(Path(sys.argv[1]))
print(json.dumps({"stats": artifact.stats,
                  "files": [n["path"] for n in artifact.nodes if n["kind"] == "file"],
                  "relationships": sorted({e["type"] for e in artifact.edges})}))
"""
    result = subprocess.run([sys.executable, "-c", script, str(ROOT)], cwd=ROOT / "atlas",
                            capture_output=True, text=True, timeout=ANALYSIS_BUDGET_SECONDS)
    assert result.returncode == 0, result.stderr
    analysis = json.loads(result.stdout)
    assert analysis["stats"]["parseErrors"] == 0
    assert analysis["stats"]["files"] >= 200
    assert analysis["stats"]["symbols"] >= 1000
    assert {"atlas/src/atlas/indexer.py", "dashboard/src/routes/index.tsx",
            "atlas/src/atlas/persistence/repositories.py"} <= set(analysis["files"])
    assert {"CALLS", "IMPORTS", "CONTAINS"} <= set(analysis["relationships"])


def menu_source():
    sources = project_sources("typescript", "menu-data")
    path = "inventory/menu.json"
    return SourceFile(path, ROOT / path, "json", sources[path].encode())


def test_data_grammars_do_not_parse_or_walk_for_impossible_calls():
    with patch("atlas.parsing.parser.get_parser") as parser:
        assert _extract_calls(menu_source()) == []
    parser.assert_not_called()


def test_default_adapter_still_extracts_calls_when_grammar_supports_them():
    sources = project_sources("ruby", "member-collision")
    path = "orders/reservations.rb"
    source = SourceFile(path, ROOT / path, "ruby", sources[path].encode())
    assert [call.evidence for call in _extract_calls(source)] == [
        'require_relative "../inventory/inventory"',
        "inventory.reserve(drink, units)", "reserve(customer, drink, units)",
        "supplier.reserve(drink, units)", "supplier.delivery_label(customer, drink, units)",
    ]


@pytest.mark.parametrize("language", ["python", "javascript", "typescript", "kotlin", "rust"])
def test_file_extraction_reuses_one_syntax_tree_per_coffee_file(language):
    sources = coffee_sources(language)
    parser = Mock(wraps=get_parser(language))
    with (
        patch("atlas.parsing.parser.get_parser", return_value=parser) as factory,
        patch("atlas.parsing.syntax.get_parser", side_effect=AssertionError("structure/imports reparsed")),
        patch("atlas.metrics.callables.get_parser", side_effect=AssertionError("metrics during parsing")),
    ):
        repo = parse_files(sources)
    parsed_sources = [source for source in sources if source.language == language]
    assert factory.call_count == len(parsed_sources)
    assert all(call.args == (language,) for call in factory.call_args_list)
    assert [call.args[0] for call in parser.parse.call_args_list] == [source.source for source in parsed_sources]
    assert_unmeasured_coffee_calls(repo)
    assert_metric_parsing_once(repo, language)


def file_callables(file):
    return [symbol for symbol in file.symbols if symbol.kind in {"function", "method"}]


def assert_unmeasured_coffee_calls(repo):
    callables = [symbol for file in repo.files for symbol in file_callables(file)]
    assert callables
    assert all(symbol.parameter_count is symbol.line_count is symbol.complexity is None for symbol in callables)
    brewer = next(file for file in repo.files if Path(file.source.path).stem.lower() == "brewer")
    assert any(call.evidence in {"self.retry(attempts - 1)", "this.retry(attempts - 1)", "retry(attempts - 1)"} for call in brewer.calls)
    assert any(file.imports for file in repo.files)


def assert_metric_parsing_once(repo, language):
    metric_parser = Mock(wraps=get_parser(language))
    with patch("atlas.metrics.callables.get_parser", return_value=metric_parser) as metric_factory:
        add_callable_metrics(repo)
    callable_files = [file for file in repo.files if file_callables(file)]
    assert metric_factory.call_count == len(callable_files)
    assert [call.args[0] for call in metric_parser.parse.call_args_list] == [file.source.source for file in callable_files]
    retry, = [symbol for symbol in repo.symbols if symbol.name == "retry"]
    assert retry.parameter_count == 1
    assert retry.line_count == (6 if language == "rust" else 4)
    assert retry.complexity is not None
    assert retry.complexity.cyclomaticComplexity == 2


def test_data_files_do_not_create_an_extra_syntax_tree():
    with (patch("atlas.parsing.parser.get_parser") as parser,
          patch("atlas.parsing.syntax.get_parser") as import_parser,
          patch("atlas.metrics.callables.get_parser") as metric_parser):
        repo = parse_files([menu_source()])
        add_callable_metrics(repo)
    parser.assert_not_called()
    import_parser.assert_not_called()
    metric_parser.assert_not_called()
    assert repo.files[0].calls == repo.files[0].symbols == repo.files[0].imports == []


def test_syntax_tree_reuse_is_local_to_each_file():
    sources = coffee_sources("python")
    parser = Mock(wraps=get_parser("python"))
    with patch("atlas.parsing.parser.get_parser", return_value=parser):
        repo = parse_files(sources)
    assert [call.args[0] for call in parser.parse.call_args_list] == [source.source for source in sources]
    assert [file.source.path for file in repo.files] == [source.path for source in sources]
    assert all(symbol.file_path == file.source.path for file in repo.files for symbol in file.symbols)


def test_import_node_lookup_indexes_each_coffee_tree_once():
    repo = parse_files(coffee_sources("python"))
    file = next(file for file in repo.files if file.source.path.endswith("brewer.py"))
    adapter = get_resolution_adapter("python")
    syntax = Syntax(file, adapter)
    with patch.object(adapter, "is_import_node", wraps=adapter.is_import_node) as predicate:
        nodes = [syntax.import_node(item.line, item.source) for item in file.imports]
        assert all(node is not None for node in nodes)
        scanned = len(syntax.nodes)
        assert predicate.call_count == scanned
        for item, node in zip(file.imports, nodes):
            assert syntax.import_node(item.line, item.source) == node
        assert syntax.import_node(0) is None
        assert predicate.call_count == scanned
        fresh = Syntax(file, adapter)
        first = file.imports[0]
        assert fresh.import_node(first.line, first.source) is not None
        assert predicate.call_count == scanned + len(fresh.nodes)


def test_syntax_tree_and_binding_scan_are_lazy_and_cached():
    repo = parse_files(coffee_sources("python"))
    file = next(file for file in repo.files if file.source.path.endswith("brewer.py"))
    with patch("atlas.metrics.resolution_syntax.get_parser", wraps=get_parser) as parser:
        syntax = Syntax(file, get_resolution_adapter("python"))
        parser.assert_not_called()
        assert "nodes" not in syntax.__dict__
        assert "bindings" not in syntax.__dict__
        assert syntax.root is syntax.root
        assert "bindings" not in syntax.__dict__
        assert syntax.bindings is syntax.bindings
        assert syntax.shadowed("attempts", file.source.source.index(b"self.retry"))
        assert syntax.spans is syntax.spans
        parser.assert_called_once_with("python")


def test_member_write_targets_are_indexed_once_per_file():
    repo = parse_files(coffee_sources("python"))
    file = next(file for file in repo.files if file.source.path.endswith("brewer.py"))
    adapter = get_resolution_adapter("python")
    syntax = Syntax(file, adapter)
    expected = sum(node.type in adapter.member_writes for node in syntax.nodes)
    assert expected > 0
    with patch.object(adapter, "write_target", wraps=adapter.write_target) as target:
        syntax.member_rebound("self", "retry")
        assert target.call_count == expected
        syntax.member_rebound("self", "other")
        syntax.member_rebound("machine", "retry")
        assert target.call_count == expected
        fresh = Syntax(file, adapter)
        fresh.member_rebound("self", "retry")
        assert target.call_count == 2 * expected


def test_path_resolution_is_cached_only_within_one_repository():
    repo = parse_files(coffee_sources("python"))
    file = next(file for file in repo.files if file.source.path.endswith("brewer.py"))
    adapter = get_resolution_adapter("python")
    syntax = {item.source.path: Syntax(item, adapter) for item in repo.files}
    modules = Modules(repo, syntax)
    imports = ImportBindings(repo, syntax, modules)
    fresh_repo = parse_files(coffee_sources("python"))
    fresh_file = next(item for item in fresh_repo.files if item.source.path == file.source.path)
    fresh_syntax = {item.source.path: Syntax(item, adapter) for item in fresh_repo.files}
    fresh = ImportBindings(fresh_repo, fresh_syntax, Modules(fresh_repo, fresh_syntax))
    with patch.object(adapter, "paths", wraps=adapter.paths) as paths:
        assert imports.path_files(file, "missing") == []
        assert imports.path_files(file, "missing") == []
        paths.assert_called_once()
        assert fresh.path_files(fresh_file, "missing") == []
        assert paths.call_count == 2
