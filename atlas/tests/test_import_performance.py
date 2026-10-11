"""Cold-process self-analysis budget and deterministic unnecessary-work guards."""

from tests.source_snapshot_fixture import case_bytes, case_text

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.resolution import ImportBindings, Modules
from atlas.parsing.discovery import SourceFile
from atlas.metrics.callables import add_callable_metrics
from atlas.parsing.parser import _extract_calls, parse_files
from atlas.metrics.resolution_syntax import Syntax
from tree_sitter_language_pack import get_parser

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_BUDGET_SECONDS = 15


def test_analyzes_this_repository_within_fast_cold_process_budget():
    # Include discovery, native parsing, resolution, validation and interpreter
    # startup. A subprocess timeout actually stops runaway work; no warm caches,
    # selected-file sampling, mocked parser, or opt-in benchmark marker.
    script = case_text("imports", "cold-analysis-script", "runner.py")
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT)],
        cwd=ROOT / "atlas",
        capture_output=True,
        text=True,
        timeout=ANALYSIS_BUDGET_SECONDS,
    )
    assert result.returncode == 0, result.stderr
    analysis = json.loads(result.stdout)
    assert analysis["stats"]["parseErrors"] == 0
    assert analysis["stats"]["files"] >= 200
    assert analysis["stats"]["symbols"] >= 1000
    assert {
        "atlas/src/atlas/indexer.py",
        "dashboard/src/routes/index.tsx",
        "atlas/src/atlas/persistence/repositories.py",
    } <= set(analysis["files"])
    assert {"CALLS", "IMPORTS", "CONTAINS"} <= set(analysis["relationships"])


def test_data_grammars_do_not_parse_or_walk_for_impossible_calls():
    source = SourceFile("data.json", ROOT / "data.json", "json", case_bytes("imports", "data-impossible-calls", 'data.json'))
    with patch("atlas.parsing.parser.get_parser") as parser:
        assert _extract_calls(source) == []
    parser.assert_not_called()


def test_default_adapter_still_extracts_calls_when_grammar_supports_them():
    source = SourceFile("main.rb", ROOT / "main.rb", "ruby", case_bytes("imports", "import-performance-default-adapter-still-extracts-calls-when-grammar-supports-them-1", 'main.rb'))
    calls = _extract_calls(source)
    assert [call.name for call in calls] == ["helper"]


@pytest.mark.parametrize(("language", "case_id"), [('python', 'syntax-reuse-python'), ('javascript', 'syntax-reuse-javascript'), ('typescript', 'syntax-reuse-typescript'), ('kotlin', 'syntax-reuse-kotlin'), ('rust', 'syntax-reuse-rust')])
def test_file_extraction_reuses_one_syntax_tree(language, case_id):
    source = SourceFile("sample", ROOT / "sample", language, case_bytes("imports", case_id, "sample"))
    parser = Mock(wraps=get_parser(language))
    with (
        patch("atlas.parsing.parser.get_parser", return_value=parser) as factory,
        patch("atlas.parsing.syntax.get_parser", side_effect=AssertionError("structure/imports reparsed")),
        patch("atlas.metrics.callables.get_parser", side_effect=AssertionError("metrics during parsing")),
    ):
        repository = parse_files([source])
    file = repository.files[0]
    factory.assert_called_once_with(language)
    parser.parse.assert_called_once_with(source.source)
    assert [call.name for call in file.calls] == ["helper"]
    callables = [symbol for symbol in file.symbols if symbol.kind in {"function", "method"}]
    assert [symbol.name for symbol in callables] == ["run"]
    assert all(symbol.parameter_count is symbol.line_count is symbol.complexity is None for symbol in callables)
    _assert_callable_metric_pass(repository, source, callables)
    if language in {"kotlin", "rust"}:
        assert file.imports


def _assert_callable_metric_pass(repository, source, callables):
    metric_parser = Mock(wraps=get_parser(source.language))
    with patch("atlas.metrics.callables.get_parser", return_value=metric_parser) as metric_factory:
        add_callable_metrics(repository)
    metric_factory.assert_called_once_with(source.language)
    metric_parser.parse.assert_called_once_with(source.source)
    assert [(symbol.name, symbol.parameter_count) for symbol in callables] == [("run", 1)]
    assert callables[0].line_count == (3 if source.language == "python" else 1)
    assert callables[0].complexity is not None
    assert callables[0].complexity.cyclomaticComplexity == 2


def test_data_files_do_not_create_an_extra_syntax_tree():
    source = SourceFile("data.json", ROOT / "data.json", "json", case_bytes("imports", "data-impossible-calls", 'data.json'))
    with (
        patch("atlas.parsing.parser.get_parser") as parser,
        patch("atlas.parsing.syntax.get_parser") as import_parser,
        patch("atlas.metrics.callables.get_parser") as metric_parser,
    ):
        repository = parse_files([source])
        add_callable_metrics(repository)
    file = repository.files[0]
    parser.assert_not_called()
    import_parser.assert_not_called()
    metric_parser.assert_not_called()
    assert file.calls == file.symbols == file.imports == []


def test_syntax_tree_reuse_is_local_to_each_file():
    sources = [
        SourceFile(f"{name}.py", ROOT / f"{name}.py", "python", case_bytes("imports", "syntax-reuse-two-files", f"{name}.py"))
        for name in ["first", "second"]
    ]
    parser = Mock(wraps=get_parser("python"))
    with patch("atlas.parsing.parser.get_parser", return_value=parser):
        repository = parse_files(sources)
    assert [call.args[0] for call in parser.parse.call_args_list] == [
        source.source for source in sources
    ]
    assert [[symbol.name for symbol in file.symbols] for file in repository.files] == [
        ["first"], ["second"]
    ]


def test_syntax_tree_and_binding_scan_are_lazy_and_cached():
    source = SourceFile("main.py", ROOT / "main.py", "python", case_bytes("imports", "import-performance-syntax-tree-and-binding-scan-are-lazy-and-cached-1", 'main.py'))
    parsed = parse_files([source]).files[0]
    with patch(
        "atlas.metrics.resolution_syntax.get_parser", wraps=get_parser
    ) as parser:
        syntax = Syntax(parsed, get_resolution_adapter("python"))
        parser.assert_not_called()
        assert "nodes" not in syntax.__dict__
        assert "bindings" not in syntax.__dict__
        assert syntax.root is syntax.root
        assert "bindings" not in syntax.__dict__
        assert syntax.bindings is syntax.bindings
        assert syntax.shadowed("x", len(source.source) - 2)
        assert syntax.spans is syntax.spans
        parser.assert_called_once_with("python")


def test_path_resolution_is_cached_only_within_one_repository():
    source = SourceFile("main.py", ROOT / "main.py", "python", case_bytes("imports", "import-performance-path-resolution-is-cached-only-within-one-repository-1", 'main.py'))
    repository = parse_files([source])
    file = repository.files[0]
    adapter = get_resolution_adapter("python")
    syntax = {file.source.path: Syntax(file, adapter)}
    modules = Modules(repository, syntax)
    with patch.object(adapter, "paths", wraps=adapter.paths) as paths:
        imports = ImportBindings(repository, syntax, modules)
        assert imports.path_files(file, "missing") == []
        assert imports.path_files(file, "missing") == []
        paths.assert_called_once()
        # Empty results are cached too, but another analysis starts fresh.
        fresh = ImportBindings(repository, syntax, modules)
        assert fresh.path_files(file, "missing") == []
        assert paths.call_count == 2
