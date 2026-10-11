"""Type-only relationships stay visible without becoming runtime cycles."""

from dataclasses import asdict

import pytest

from atlas.metrics.artifact import GraphArtifact
from atlas.metrics.cycles import circular_dependencies
from tests.import_project_support import analyze, project_sources, repository, symbols

BACK_REFERENCES = [
    ("type { orderStock }", False),
    ("type StockOrder", False),
    ("type * as StockOrder", False),
    ("{ type StockOrder }", False),
    ("{ /* receipt */ type StockOrder, type Options }", False),
    ("{ type StockOrder, orderStock }", True),
    ("StockOrder, { type Options }", True),
    ("{ type as StockOrder }", True),
    ("{ orderStock }", True),
    (None, True),
    ("{}", True),
]


@pytest.mark.parametrize("clause,runtime", BACK_REFERENCES)
def test_typescript_stock_back_references(tmp_path, clause, runtime):
    sources = project_sources("typescript", "stock-back-reference")
    path = "inventory/Stock.ts"
    evidence = (f'import {clause} from "../ordering/StockOrder.ts";' if clause is not None
                else 'import "../ordering/StockOrder.ts";')
    sources[path] = evidence + '\nexport const stock = 12;\n'
    artifact = analyze(tmp_path, sources)
    back_reference, = [edge for edge in artifact.edges if edge["type"] == "IMPORTS" and edge["path"] == path]
    assert back_reference["evidence"] == evidence
    assert back_reference["targetStableKey"] == "file:ordering/StockOrder.ts"
    assert back_reference.get("typeOnly", False) is not runtime
    assert artifact.circularDependencies is not None
    group = {"file:inventory/Stock.ts", "file:ordering/StockOrder.ts"}
    assert cycle_keys_touching(artifact, group) == ([group] if runtime else [])
    restored = GraphArtifact(**asdict(artifact))
    assert circular_dependencies([dict(node) for node in restored.nodes], [dict(edge) for edge in restored.edges]) == artifact.circularDependencies


def cycle_keys_touching(artifact, keys):
    assert artifact.circularDependencies is not None
    return [set(item["nodeStableKeys"]) for item in artifact.circularDependencies["groups"]
            if set(item["nodeStableKeys"]) & keys]


def package_project(initializer):
    sources = project_sources("python")
    sources["src/coffee/tasting/__init__.py"] = initializer
    return sources


def imports_at(artifact, path):
    return [edge for edge in artifact.edges if edge["type"] == "IMPORTS" and edge["path"] == path]


def groups_at(artifact, keys):
    assert artifact.circularDependencies is not None
    return [group for group in artifact.circularDependencies["groups"] if set(group["nodeStableKeys"]) == keys]


def test_python_package_child_imports(tmp_path):
    path = "src/coffee/tasting/__init__.py"
    sources = package_project("from . import (\n    espresso, filter\n)\nfrom . import receipt as report\n")
    for child in ("espresso.py", "filter/__init__.py", "receipt.py"):
        sources["src/coffee/tasting/" + child] = ""
    artifact = analyze(tmp_path, sources)
    imports = imports_at(artifact, path)
    assert {edge["targetStableKey"] for edge in imports} == {
        "file:src/coffee/tasting/espresso.py", "file:src/coffee/tasting/filter/__init__.py", "file:src/coffee/tasting/receipt.py",
    }
    assert {edge["evidence"] for edge in imports} == {"from . import (\n    espresso, filter\n)", "from . import receipt as report"}
    assert artifact.circularDependencies is not None
    assert all("file:" + path not in group["nodeStableKeys"] for group in artifact.circularDependencies["groups"])


@pytest.mark.parametrize("evidence", ["import coffee.tasting", "from coffee import tasting"])
def test_python_actual_self_imports(tmp_path, evidence):
    artifact = analyze(tmp_path, package_project(evidence + "\n"))
    assert groups_at(artifact, {"file:src/coffee/tasting/__init__.py"})


def test_python_runtime_child_cycle(tmp_path):
    sources = package_project("from . import espresso\n")
    sources["src/coffee/tasting/espresso.py"] = "import coffee.tasting\n"
    artifact = analyze(tmp_path, sources)
    assert groups_at(artifact, {"file:src/coffee/tasting/__init__.py", "file:src/coffee/tasting/espresso.py"})


def test_python_unresolved_child_stays_external(tmp_path):
    path = "src/coffee/tasting/__init__.py"
    artifact = analyze(tmp_path, package_project("from . import missing\n"))
    edge, = imports_at(artifact, path)
    assert edge["targetStableKey"] == "external:python:module:.missing"
    assert edge["confidence"] == "EXTRACTED"
    assert edge["evidence"] == "from . import missing"


def test_python_package_attribute_does_not_become_self_import(tmp_path):
    path = "src/coffee/tasting/__init__.py"
    sources = package_project("def portions(): return 2\nfrom . import portions\n")
    artifact = analyze(tmp_path, sources)
    repo = repository("python", sources)
    edge, = imports_at(artifact, path)
    assert edge["targetStableKey"] == symbols(repo, path, "portions")[0].key
    assert artifact.circularDependencies is not None
    assert all("file:" + path not in group["nodeStableKeys"] for group in artifact.circularDependencies["groups"])


def test_type_only_external_import_remains_visible(tmp_path):
    sources = project_sources("typescript")
    path = "ordering/Delivery.ts"
    sources[path] = 'import type { Delivery } from "missing";\n'
    artifact = analyze(tmp_path, sources)
    edge, = imports_at(artifact, path)
    assert edge["evidence"] is not None and edge["evidence"] in sources[path]
    assert edge["targetStableKey"] == "external:typescript:module:missing"
    assert edge.get("typeOnly") is True
    assert edge["confidence"] == "EXTRACTED"
