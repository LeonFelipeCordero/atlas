"""Cold-process self-analysis budget and deterministic unnecessary-work guards."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from atlas.adapters import get_resolution_adapter
from atlas.adapters.resolution import ImportBindings, Modules
from atlas.discovery import SourceFile
from atlas.extraction.parser import _extract_calls, parse_files
from atlas.extraction.resolution_syntax import Syntax
from tree_sitter_language_pack import get_parser

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_BUDGET_SECONDS = 15


def test_analyzes_this_repository_within_fast_cold_process_budget():
    # Include discovery, native parsing, resolution, validation and interpreter
    # startup. A subprocess timeout actually stops runaway work; no warm caches,
    # selected-file sampling, mocked parser, or opt-in benchmark marker.
    script = """
import json
import sys
from pathlib import Path
from atlas.indexer import analyze_repository
artifact = analyze_repository(Path(sys.argv[1]))
print(json.dumps({"stats": artifact.stats,
                  "files": [n["path"] for n in artifact.nodes if n["kind"] == "file"],
                  "relationships": sorted({e["type"] for e in artifact.edges})}))
"""
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
        "atlas/src/atlas/persistence/normalized_schema.py",
    } <= set(analysis["files"])
    assert {"CALLS", "IMPORTS", "CONTAINS"} <= set(analysis["relationships"])


def test_data_grammars_do_not_parse_or_walk_for_impossible_calls():
    source = SourceFile("data.json", ROOT / "data.json", "json", b'{"call": "run()"}')
    with patch("atlas.extraction.parser.get_parser") as parser:
        assert _extract_calls(source) == []
    parser.assert_not_called()


def test_default_adapter_still_extracts_calls_when_grammar_supports_them():
    source = SourceFile("main.rb", ROOT / "main.rb", "ruby", b"helper()\n")
    calls = _extract_calls(source)
    assert [call.name for call in calls] == ["helper"]


def test_syntax_tree_and_binding_scan_are_lazy_and_cached():
    source = SourceFile("main.py", ROOT / "main.py", "python", b"x = 1\nx()\n")
    parsed = parse_files([source]).files[0]
    with patch(
        "atlas.extraction.resolution_syntax.get_parser", wraps=get_parser
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
    source = SourceFile("main.py", ROOT / "main.py", "python", b"pass\n")
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
