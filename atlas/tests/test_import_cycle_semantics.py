"""Runtime cycle semantics without deleting useful static import relationships."""

from tests.import_snapshot_support import import_case_sources as case_sources

from dataclasses import asdict
from pathlib import Path

import pytest

from atlas.metrics.artifact import GraphArtifact
from atlas.metrics.cycles import circular_dependencies
from atlas.indexer import analyze_repository


def analyze_files(root: Path, files: dict[str, str]) -> GraphArtifact:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return analyze_repository(root)


@pytest.mark.parametrize('case_id,runtime', [('import-cycle-semantics-typescript-back-references-1', False), ('import-cycle-semantics-typescript-back-references-2', False), ('import-cycle-semantics-typescript-back-references-3', False), ('import-cycle-semantics-typescript-back-references-4', False), ('import-cycle-semantics-typescript-back-references-5', False), ('import-cycle-semantics-typescript-back-references-6', True), ('import-cycle-semantics-typescript-back-references-7', True), ('import-cycle-semantics-typescript-back-references-8', True), ('import-cycle-semantics-typescript-back-references-9', True), ('import-cycle-semantics-typescript-back-references-10', True), ('import-cycle-semantics-typescript-back-references-11', True)])
def test_typescript_back_references(tmp_path, case_id, runtime):
    artifact = analyze_files(
        tmp_path,
        case_sources("imports", case_id),
    )
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    back_reference = next(
        edge for edge in imports if edge["path"] == "routeTree.gen.ts"
    )
    assert back_reference["targetStableKey"] == "file:router.tsx"
    assert back_reference.get("typeOnly", False) is not runtime
    assert artifact.circularDependencies is not None
    assert bool(artifact.circularDependencies["groups"]) is runtime
    # Optional metadata survives strict artifact validation and saved JSON roundtrips.
    restored = GraphArtifact(**asdict(artifact))
    assert (
        circular_dependencies(
            [dict(node) for node in restored.nodes],
            [dict(edge) for edge in restored.edges],
        )
        == artifact.circularDependencies
    )


def test_python_package_child_imports(tmp_path: Path):
    artifact = analyze_files(
        tmp_path,
        case_sources("imports", "import-cycle-semantics-python-package-child-imports"),
    )
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    assert {edge["targetStableKey"] for edge in imports} == {
        "file:pkg/elixir.py",
        "file:pkg/go/__init__.py",
        "file:pkg/javascript.py",
    }
    assert {edge["evidence"] for edge in imports} == {
        "from . import (\n    elixir, go\n)",
        "from . import javascript as script",
    }
    assert artifact.circularDependencies == {"version": 1, "groups": []}


@pytest.mark.parametrize(('case_id',), [('import-cycle-semantics-python-actual-self-imports-1',), ('import-cycle-semantics-python-actual-self-imports-2',)])
def test_python_actual_self_imports(tmp_path, case_id):
    artifact = analyze_files(tmp_path, case_sources("imports", case_id))
    assert artifact.circularDependencies is not None
    assert artifact.circularDependencies["groups"][0]["nodeStableKeys"] == [
        "file:pkg/__init__.py"
    ]


def test_python_runtime_child_cycle(tmp_path: Path):
    artifact = analyze_files(
        tmp_path,
        case_sources("imports", "import-cycle-semantics-python-runtime-child-cycle"),
    )
    assert artifact.circularDependencies is not None
    assert artifact.circularDependencies["groups"][0]["nodeStableKeys"] == [
        "file:pkg/__init__.py",
        "file:pkg/child.py",
    ]


def test_python_unresolved_child_stays_external(tmp_path: Path):
    artifact = analyze_files(tmp_path, case_sources("imports", "import-cycle-semantics-python-unresolved-child-stays-external"))
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"] == "external:python:module:.missing"
    assert edge["confidence"] == "EXTRACTED"


def test_python_package_attribute_does_not_become_self_import(tmp_path: Path):
    artifact = analyze_files(
        tmp_path,
        case_sources("imports", "import-cycle-semantics-python-package-attribute-does-not-become-self-import"),
    )
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"].startswith("symbol:pkg/__init__.py::work")
    assert artifact.circularDependencies == {"version": 1, "groups": []}


def test_type_only_external_import_remains_visible(tmp_path: Path):
    artifact = analyze_files(tmp_path, case_sources("imports", "import-cycle-semantics-type-only-external-import-remains-visible"))
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"] == "external:typescript:module:missing"
    assert edge.get("typeOnly") is True
    assert edge["confidence"] == "EXTRACTED"
