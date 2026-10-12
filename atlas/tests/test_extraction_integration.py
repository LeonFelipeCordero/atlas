"""Coffee grammar facts survive resolution, including unsafe syntax boundaries."""

from atlas.metrics.resolver import resolve_connections
from tests.import_project_support import (
    assert_call, assert_external, project_repository, project_sources, repository, symbols,
)


def test_elixir_heads_controls_nested_arguments_and_pipelines():
    repo = project_repository("elixir", "tasting-pipelines")
    path = "brewing/tasting.ex"
    file = next(file for file in repo.files if file.source.path == path)
    assert [call.evidence for call in file.calls if call.name == "retry"] == ["retry(n - 1)"]
    assert not {"def", "defmodule", "if", "case"} & {call.name for call in file.calls}
    for evidence in ('brew([])', 'brew', 'brew(["espresso"])', 'brew(["filter"])'):
        assert len(assert_call(repo, (path, evidence), (path, "Coffee.Brewing.Tasting.brew"))) == 2
    recursion = assert_call(repo, (path, "retry(n - 1)"), (path, "Coffee.Brewing.Tasting.retry"))
    assert len(recursion) == 2
    assert sum(edge.source_key == edge.target_key for edge in recursion) == 1


def test_rust_macro_nested_arguments_offsets_and_invalid_dsl():
    repo = project_repository("rust", "receipt-macros")
    path = "brewing/tasting.rs"
    file = next(file for file in repo.files if file.source.path == path)
    inner, = [call for call in file.calls if call.name == "tasting"]
    assert inner.start_byte == file.source.source.rindex(b"tasting()")
    assert inner.line == 4
    assert inner.evidence == "tasting()"
    assert file.source.source[inner.start_byte:inner.end_byte] == b"tasting()"
    assert_call(repo, (path, "tasting()"), (path, "tasting"))
    assert {"println!", "format!", "receipt!"} <= {call.name for call in file.calls}
    assert "missing" not in {call.name for call in file.calls}
    assert_invalid_receipt_macros(repo, file)


def assert_invalid_receipt_macros(repo, file):
    for call in file.calls:
        if call.name == "receipt!":
            assert_external(repo, file.source.path, call.evidence)


def test_rust_relative_module_paths_keep_declared_identity():
    sources = project_sources("rust", "nested-receipt-modules")
    sources["brewing/mod.rs"] += "\npub mod tasting;\n"
    sources["main.rs"] += "\nfn print_tasting() { crate::brewing::tasting::tasting(); }\n"
    repo = repository("rust", sources)
    assert_call(repo, ("main.rs", "crate::brewing::tasting::tasting()"), ("brewing/tasting.rs", "tasting"))
    assert_call(repo, ("brewing/tasting.rs", "self::receipt::render()"), ("brewing/tasting/receipt.rs", "render"))
    imports = [edge for edge in resolve_connections(repo).connections if edge.type == "IMPORTS" and edge.path == "brewing/tasting.rs"]
    assert len(imports) == 1
    assert imports[0].evidence == "mod receipt;"
    assert imports[0].target_key == "file:brewing/tasting/receipt.rs"


def test_inheritance_headers_and_import_aliases_are_precise():
    repo = project_repository("python", "aliased-brewing-base")
    inherited = [edge for edge in resolve_connections(repo).connections if edge.type == "INHERITS" and edge.path == "src/coffee/brewing/tasting.py"]
    assert len(inherited) == 1
    assert inherited[0].target_key == symbols(repo, "src/coffee/brewing/brewer.py", "Brewing")[0].key
    repo = project_repository("java", "wrong-brewing-package")
    inherited = [edge for edge in resolve_connections(repo).connections if edge.type == "INHERITS" and edge.path == "orders/Tasting.java"]
    assert len(inherited) == 1
    assert inherited[0].target_key.startswith("external:")


def test_multiple_bases_exclude_metaclass_arguments():
    repo = project_repository("python", "multiple-brewing-bases")
    flight, = symbols(repo, "src/coffee/brewing/tasting.py", "Flight")
    bases = [item.target_name for item in repo.inheritances if item.source_key == flight.key]
    assert bases == ["Tasting", "Cupping"]
