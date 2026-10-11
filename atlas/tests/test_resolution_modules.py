"""Rust receipt module layouts remain scoped within complete coffee projects."""

import pytest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.rust import RustModules
from atlas.metrics.resolution_syntax import Syntax
from atlas.metrics.resolver import resolve_connections
from tests.test_resolution_lexical_safety import assert_order_call, order_symbol_keys
from tests.test_semantic_resolution import repository
from tests.variant_snapshot_support import VARIANT_ROOT, scenario_sources


def receipt_sources():
    return {source.path: source.source.decode() for source in scenario_sources(
        VARIANT_ROOT / "rust" / "receipt-module-layout"
    )}


def receipt_repository(sources=None):
    return repository("rust", receipt_sources() if sources is None else sources)


def modules(repo):
    return RustModules(repo, {f.source.path: Syntax(f, get_resolution_adapter("rust")) for f in repo.files})


def assert_receipt(repo, case, caller=("main.rs", "main")):
    evidence, path = case
    source, owner = caller
    return assert_order_call(repo, (source, owner, evidence), (path, "render") if path else None)


def rust_paths(files):
    return [file.source.path for file in files]


def assert_printer_imports(repo):
    imports = [e for e in resolve_connections(repo).connections
               if e.type == "IMPORTS" and e.evidence == "use crate::receipt::print as printer;"]
    assert imports
    assert {e.target_key for e in imports} == {"file:receipt/print.rs"}


def assert_module_visibility(repo, case):
    path, name, public = case
    file = next(f for f in repo.files if f.source.path == path)
    symbol = next(s for s in file.symbols if s.qualified_name == f"{path}::{name}")
    syntax = Syntax(file, get_resolution_adapter("rust"))
    node = syntax.node(symbol.start_byte, symbol.end_byte)
    assert node is not None
    assert any(c.type == "visibility_modifier" for c in node.named_children) == public


def test_external_module_owner_is_not_a_second_crate_root():
    repo = receipt_repository()
    assert_receipt(repo, ("crate::print::render(&names)", None))
    assert_receipt(repo, ("crate::receipt::print::render(&names)", "receipt/print.rs"))
    assert modules(repo).rust_files("crate::print") == []
    assert modules(repo).rust_files("crate::daily") == []


def test_inline_ancestry_selects_nested_file_not_root_decoy():
    sources = receipt_sources()
    sources["main.rs"] = sources["main.rs"].replace("mod receipt;", "mod receipt { pub mod print; }")
    repo = receipt_repository(sources)
    assert_receipt(repo, ("crate::receipt::print::render(&names)", "receipt/print.rs"))
    assert_receipt(repo, ("crate::print::render(&names)", None))


def test_deep_inline_modules_mod_rs_and_file_stem_layout():
    repo = receipt_repository()
    assert_receipt(repo, ("daily::ledger::print::render(names)", "receipt/daily/ledger/print/mod.rs"),
                   ("receipt.rs", "close"))
    sources = receipt_sources()
    sources["main.rs"] = sources["main.rs"].replace(
        "mod receipt;", "mod receipt { pub mod daily { pub mod ledger { pub mod print; } } }"
    )
    sources["main.rs"] = sources["main.rs"].replace(
        "crate::receipt::print::render(&names)", "crate::receipt::daily::ledger::print::render(&names)"
    )
    # The same application can live under Cargo's conventional src directory.
    repo = receipt_repository({f"src/{path}": text for path, text in sources.items()})
    assert_receipt(repo, ("crate::receipt::daily::ledger::print::render(&names)",
                   "src/receipt/daily/ledger/print/mod.rs"), ("src/main.rs", "main"))
    assert [f.source.path for f in modules(repo).rust_files("crate::receipt::daily::ledger::print")] == [
        "src/receipt/daily/ledger/print/mod.rs"
    ]


def test_external_path_attribute_is_relative_to_containing_file():
    repo = receipt_repository()
    assert_receipt(repo, ("custom::render(names)", "special/receipt_printer.rs"), ("receipt.rs", "close"))
    file = next(f for f in repo.files if f.source.path == "receipt.rs")
    index = modules(repo)
    assert [f.source.path for f in index.rust_import(file, "self::custom", 0)] == ["special/receipt_printer.rs"]
    assert index.rust_import(file, "crate::custom", 0) == []


def test_inline_path_attributes_use_inline_directory():
    repo = receipt_repository()
    assert_receipt(repo, ("seasonal::print::render(names)", "special/receipt_printer.rs"), ("receipt.rs", "close"))
    assert_receipt(repo, ("alternate::print::render(names)", "receipt/alternate/print.rs"), ("receipt.rs", "close"))
    sources = receipt_sources()
    sources["main.rs"] = sources["main.rs"].replace(
        "mod receipt;", '#[path = "receipt"]\nmod receipt { pub mod print; }'
    )
    assert_receipt(receipt_repository(sources), ("crate::receipt::print::render(&names)", "receipt/print.rs"))


def test_nonstandard_coffee_root_excludes_referenced_module_owners():
    sources = receipt_sources()
    sources["coffee.rs"] = sources.pop("main.rs").replace(
        "mod brewing;", '#[path = "brewing/mod.rs"]\nmod brewing;'
    ).replace("mod reporting;", '#[path = "reporting/mod.rs"]\nmod reporting;')
    # Leave the unused kiosk printer a leaf, not an additional application entry.
    sources["print.rs"] = sources["print.rs"].replace("pub mod daily;\n\n", "")
    repo = receipt_repository(sources)
    assert_receipt(repo, ("crate::receipt::print::render(&names)", "receipt/print.rs"), ("coffee.rs", "main"))
    assert_receipt(repo, ("crate::print::render(&names)", None), ("coffee.rs", "main"))
    assert_order_call(repo, ("coffee.rs", "main", 'crate::brewing::recipe::preview("espresso")'),
                      ("brewing/recipe.rs", "preview"))
    assert_order_call(repo, ("brewing/brewer.rs", "brew", "report::render(&[])"), ("reporting/report.rs", "render"))


@pytest.mark.parametrize("entry", ["main.rs", "coffee.rs"])
def test_multiple_roots_remain_ambiguous(entry):
    sources = receipt_sources()
    source = sources.pop("main.rs")
    sources[entry] = source
    sources["lib.rs" if entry == "main.rs" else "kiosk.rs"] = source
    repo = receipt_repository(sources)
    assert_receipt(repo, ("crate::receipt::print::render(&names)", None), (entry, "main"))
    assert modules(repo).rust_files("crate::receipt::print") == []


def test_relative_module_aliases_require_inline_lexical_position():
    sources = receipt_sources()
    sources["main.rs"] = sources["main.rs"].replace(
        "mod receipt;", "mod print;\nmod receipt { pub mod print; }"
    )
    repo = receipt_repository(sources)
    index = modules(repo)
    file = next(f for f in repo.files if f.source.path == "main.rs")
    position = file.source.source.index(b"pub mod print;")
    for name in ("print", "self::print"):
        assert rust_paths(index.rust_import(file, name, position)) == ["receipt/print.rs"]
    assert [f.source.path for f in index.rust_import(file, "super::print", position)] == ["print.rs"]
    assert [f.source.path for f in index.rust_import(file, "print", 0)] == ["print.rs"]
    assert index.rust_import(file, "super::print", 0) == []


def test_inline_namespaces_expose_only_direct_symbols_and_import_scopes():
    repo = receipt_repository()
    index = modules(repo)
    file = next(f for f in repo.files if f.source.path == "main.rs")
    assert index.rust_import(file, "crate::counter") == []
    actual = index.rust_symbols(file, "crate::counter")
    expected = order_symbol_keys(repo, ("main.rs", "counter.close")) | order_symbol_keys(repo, ("main.rs", "counter.nested"))
    assert len(expected) == 2
    assert {s.key for s in actual} == expected
    assert_receipt(repo, ("printer::render(names)", "receipt/print.rs"), ("main.rs", "counter.close"))
    assert_receipt(repo, ("printer::render(&names)", None))
    assert_printer_imports(repo)


def test_module_visibility_syntax_is_preserved():
    repo = receipt_repository()
    for case in (("receipt.rs", "render", True), ("receipt.rs", "audit", False),
                 ("main.rs", "counter", False), ("main.rs", "counter.close", True)):
        assert_module_visibility(repo, case)
    assert_receipt(repo, ("self::print::render(names)", "receipt/print.rs"), ("receipt.rs", "close"))
    assert_receipt(repo, ("super::receipt::print::render(names)", "receipt/print.rs"), ("receipt.rs", "close"))


def test_recursive_path_module_graph_terminates_without_false_root():
    sources = receipt_sources()
    sources["receipt.rs"] = sources["receipt.rs"].replace(
        "pub mod print;", '#[path = "receipt.rs"]\npub mod print;', 1
    )
    repo = receipt_repository(sources)
    assert_receipt(repo, ("crate::print::render(&names)", None))
    assert modules(repo).rust_files("crate::receipt::print::print") == []
