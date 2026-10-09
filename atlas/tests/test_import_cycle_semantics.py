"""Runtime cycle semantics without deleting useful static import relationships."""

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


@pytest.mark.parametrize(
    "statement, runtime",
    [
        ("import type { getRouter } from './router.tsx';", False),
        ("import type Router from './router.tsx';", False),
        ("import type * as Router from './router.tsx';", False),
        ("import { type Router } from './router.tsx';", False),
        ("import { /* note */ type Router, type Options } from './router.tsx';", False),
        ("import { type Router, getRouter } from './router.tsx';", True),
        ("import Router, { type Options } from './router.tsx';", True),
        ("import { type as Router } from './router.tsx';", True),
        ("import { getRouter } from './router.tsx';", True),
        ("import './router.tsx';", True),
        ("import {} from './router.tsx';", True),
    ],
)
def test_typescript_back_references(tmp_path: Path, statement: str, runtime: bool):
    artifact = analyze_files(
        tmp_path,
        {
            "routeTree.gen.ts": statement,
            "router.tsx": "import { routeTree } from './routeTree.gen';\n"
            "export function getRouter() {}\nexport type Router = {};\n",
        },
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
        {
            "pkg/__init__.py": "from . import (\n    elixir, go\n)\n"
            "from . import javascript as script\n",
            "pkg/elixir.py": "",
            "pkg/go/__init__.py": "",
            "pkg/javascript.py": "",
        },
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


@pytest.mark.parametrize("statement", ["import pkg", "from . import __init__"])
def test_python_actual_self_imports(tmp_path: Path, statement: str):
    artifact = analyze_files(tmp_path, {"pkg/__init__.py": statement})
    assert artifact.circularDependencies is not None
    assert artifact.circularDependencies["groups"][0]["nodeStableKeys"] == [
        "file:pkg/__init__.py"
    ]


def test_python_runtime_child_cycle(tmp_path: Path):
    artifact = analyze_files(
        tmp_path,
        {"pkg/__init__.py": "from . import child", "pkg/child.py": "import pkg"},
    )
    assert artifact.circularDependencies is not None
    assert artifact.circularDependencies["groups"][0]["nodeStableKeys"] == [
        "file:pkg/__init__.py",
        "file:pkg/child.py",
    ]


def test_python_unresolved_child_stays_external(tmp_path: Path):
    artifact = analyze_files(tmp_path, {"pkg/__init__.py": "from . import missing"})
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"] == "external:python:module:.missing"
    assert edge["confidence"] == "EXTRACTED"


def test_python_package_attribute_does_not_become_self_import(tmp_path: Path):
    artifact = analyze_files(
        tmp_path,
        {"pkg/__init__.py": "def work(): pass\nfrom . import work"},
    )
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"].startswith("symbol:pkg/__init__.py::work")
    assert artifact.circularDependencies == {"version": 1, "groups": []}


def test_type_only_external_import_remains_visible(tmp_path: Path):
    artifact = analyze_files(tmp_path, {"a.ts": "import type { T } from 'missing';"})
    edge = next(edge for edge in artifact.edges if edge["type"] == "IMPORTS")
    assert edge["targetStableKey"] == "external:typescript:module:missing"
    assert edge.get("typeOnly") is True
    assert edge["confidence"] == "EXTRACTED"
