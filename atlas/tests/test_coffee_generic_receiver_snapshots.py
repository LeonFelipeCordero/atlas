"""Physical, offline grammar evidence and exact production receiver targets."""

import json
from pathlib import Path

import pytest

from atlas.indexer import analyze_repository
from atlas.metrics.adapters import SUPPORTED_LANGUAGES, get_resolution_adapter, receiver_coverage
from atlas.metrics.resolution_syntax import Syntax
from atlas.parsing.discovery import discover_files
from atlas.parsing.parser import parse_files
from atlas.syntax import field, text

ROOT = Path(__file__).parent / "fixtures/coffee/generic_receivers"
SNAPSHOTS = Path(__file__).parent / "snapshots/generic_receivers"


@pytest.mark.parametrize("language", ["csharp", "ruby", "php"])
def test_generic_receiver_pipeline_snapshot(language):
    graph = analyze_repository((ROOT / language).resolve())
    nodes = {n["stableKey"]: n for n in graph.nodes}
    actual = [
        [nodes[e["sourceStableKey"]]["qualifiedName"], e["evidence"], e["targetStableKey"]]
        for e in graph.edges if e["type"] == "CALLS"
    ]
    assert actual == json.loads((SNAPSHOTS / f"{language}.json").read_text())


@pytest.mark.parametrize("language", ["csharp", "ruby", "php"])
def test_generic_hooks_verified_against_physical_grammar(language):
    repo = parse_files(discover_files((ROOT / language).resolve()))
    adapter = get_resolution_adapter(language)
    syntaxes = [Syntax(file, adapter) for file in repo.files]
    assert all(valid_syntax(s) for s in syntaxes)
    file = next(f for f in repo.files if Path(f.source.path).name.lower().startswith("ledger."))
    syntax = Syntax(file, adapter)
    assert receiver_bindings_snapshot(syntax) == json.loads((SNAPSHOTS / f"{language}_bindings.json").read_text())
    if language == "php":
        assert_php_invocations(syntax, adapter)


def receiver_bindings_snapshot(syntax):
    bindings = [b for n in syntax.nodes for b in syntax.adapter.receiver_bindings(syntax, n)]
    return [[b.name, b.annotation, b.inferred, text(b.node)] for b in bindings]


def valid_syntax(syntax):
    return syntax.root is not None and not syntax.root.has_error


def assert_php_invocations(syntax, adapter):
    # Every physical member invocation must reach production resolution.
    calls = [n for n in syntax.nodes if n.type == "member_call_expression"]
    assert len(calls) == 9
    assert all(text(adapter.call_target(n)[0]) == "record" for n in calls)
    direct = next(n for n in calls if text(field(n, "object")).startswith("(new"))
    _, receiver = adapter.call_target(direct)
    assert receiver is not None and receiver.type == "object_creation_expression"
    assert text(adapter.call_target(receiver)[0]) == "Ledger"
    assert sum("->record" in c.evidence for c in syntax.file.calls) == 9


@pytest.mark.parametrize("case", [
    ("csharp", ["Ledger.cs::Intake.GenericMethod", "Ledger.cs::Intake.GenericLocal",
                "Ledger.cs::Intake.Constrained", "Ledger.cs::GenericIntake.GenericClass",
                "Ledger.cs::GenericIntake.Nested.GenericNested"],
     "ledger.Record()", "external:csharp:callable:Record"),
    ("ruby", [f"ledger.rb::{name}" for name in [
        "block_defaults", "block_keywords", "block_destructured", "brace_defaults",
        "method_default", "method_keyword", "method_destructured"]],
     "ledger.record", "external:ruby:callable:record"),
    ("php", ["imported.php::imported", "imported.php::imported_new",
             "namespaced.php::namespaced", "namespaced.php::namespaced_new",
             "ledger.php::nullable", "ledger.php::union_type", "ledger.php::intersection_type"],
     "$ledger->record()", "external:php:callable:record"),
    ("php", ["imported.php::imported_direct", "namespaced.php::namespaced_direct"],
     "(new Ledger())->record()", "external:php:callable:record"),
])
def test_unsafe_generic_receivers_have_exact_unresolved_targets(case):
    language, owners, evidence, target = case
    graph = analyze_repository((ROOT / language).resolve())
    nodes = {n["stableKey"]: n for n in graph.nodes}
    actual = sorted(
        [nodes[e["sourceStableKey"]]["qualifiedName"], e["evidence"], e["targetStableKey"]]
        for e in graph.edges if e["type"] == "CALLS"
        and nodes[e["sourceStableKey"]]["qualifiedName"] in owners and e["evidence"] == evidence
    )
    assert actual == sorted([owner, evidence, target] for owner in owners)


def test_catalog_coverage_inventory():
    coverage = receiver_coverage()
    assert set(coverage) == SUPPORTED_LANGUAGES
    assert json.loads(json.dumps(coverage)) == coverage
    assert {k for k, v in coverage.items() if v["hooks"]} == {"csharp", "php", "ruby"}
    assert coverage["json"]["status"] == "generic"
    assert coverage["python"]["status"] == "dedicated"
    assert not get_resolution_adapter("json").receiver_class_nodes
