"""Python project layouts must produce local dependencies, not external guesses."""

from dataclasses import asdict
from pathlib import Path

import pytest

from atlas.domain.report import build_artifact_report
from atlas.indexer import analyze_repository


def analyze(root: Path, sources: dict[str, str]):
    for path, source in sources.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    return analyze_repository(root)


@pytest.mark.parametrize("prefix", ["", "src/", "services/backend/", "services/backend/src/"])
@pytest.mark.parametrize("relationship", ["IMPORTS", "CALLS", "INHERITS"])
def test_package_imports_resolve_independently_of_analysis_root(tmp_path, prefix, relationship):
    artifact = analyze(tmp_path, {
        prefix + "app/__init__.py": "",
        prefix + "app/main.py": "from app.worker import Worker\nclass Runner(Worker): pass\nWorker.work()\n",
        prefix + "app/worker.py": "class Worker:\n @staticmethod\n def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] == relationship]
    assert edges
    assert all(prefix + "app/worker.py" in edge["targetStableKey"] for edge in edges)
    assert build_artifact_report(asdict(artifact))["findings"] == []


def test_src_namespace_package(tmp_path):
    artifact = analyze(tmp_path, {
        "src/app/main.py": "import app.worker as worker\nworker.work()\n",
        "src/app/worker.py": "def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize("statement", ["from . import worker as w", "from app import worker as w", "from . import (\n worker as w,\n)"])
def test_child_module_imports_link_and_bind_namespace(tmp_path, statement):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": "",
        "src/app/main.py": statement + "\nw.work()\n",
        "src/app/worker.py": "def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


def test_comma_separated_module_imports(tmp_path):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": "",
        "main.py": "import app.worker as w, app.other as o\nw.work()\no.work()\n",
        "src/app/worker.py": "def work(): pass\n",
        "src/app/other.py": "def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 4
    assert all(not edge["targetStableKey"].startswith("external:") for edge in edges)


def test_duplicate_source_roots_are_ambiguous(tmp_path):
    artifact = analyze(tmp_path, {
        "main.py": "import app.worker as w\nw.work()\n",
        "one/src/app/worker.py": "def work(): pass\n",
        "two/src/app/worker.py": "def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


def test_unrelated_suffix_is_not_an_import_root(tmp_path):
    artifact = analyze(tmp_path, {
        "main.py": "import requests\nrequests.get()\n",
        "examples/requests.py": "def get(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


@pytest.mark.parametrize("module", ["app/worker", "app/worker/__init__"])
def test_runtime_modules_take_precedence_over_type_stubs(tmp_path, module):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": "",
        "main.py": "import app.worker as w\nw.work()\n",
        "src/" + module + ".py": "def work(): pass\n",
        "src/" + module + ".pyi": "def work() -> None: ...\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/" + module + ".py" in edge["targetStableKey"] for edge in edges)
    assert all(".pyi" not in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize("attribute", ["worker = None", "from other import value as worker", "import other as worker"])
@pytest.mark.parametrize("statement", ["from app import worker as w", "from . import worker as w"])
def test_package_attributes_prevent_child_module_guesses(tmp_path, attribute, statement):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": attribute + "\n",
        "src/app/main.py": statement + "\nw.work()\n",
        "src/app/worker.py": "def work(): pass\n",
    })
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
    assert len(calls) == 1
    assert calls[0]["targetStableKey"].startswith("external:")
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    assert all("app/worker.py" not in edge["targetStableKey"] for edge in imports)


@pytest.mark.parametrize("statement", ["from app import worker as w", "from . import worker as w"])
def test_annotation_only_attribute_does_not_hide_child_module(tmp_path, statement):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": "worker: object\n",
        "src/app/main.py": statement + "\nw.work()\n",
        "src/app/worker.py": "def work(): pass\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize("statement", ["from app import worker as w", "import app.worker as w"])
def test_ambiguous_parent_package_cannot_resolve_unique_child(tmp_path, statement):
    artifact = analyze(tmp_path, {
        "main.py": statement + "\nw.work()\n",
        "one/src/app/__init__.py": "",
        "one/src/app/worker.py": "def work(): pass\n",
        "two/src/app/__init__.py": "worker = None\n",
    })
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


@pytest.mark.parametrize("statement", ["from app import worker as w", "import app.worker as w"])
def test_ordinary_module_cannot_have_child_modules(tmp_path, statement):
    artifact = analyze(tmp_path, {
        "main.py": statement + "\nw.work()\n",
        "app.py": "",
        "app/worker.py": "def work(): pass\n",
    })
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
    assert len(calls) == 1
    assert calls[0]["targetStableKey"].startswith("external:")
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    assert all("app/worker.py" not in edge["targetStableKey"] for edge in imports)


def test_absolute_src_import_cycle_is_reported(tmp_path):
    artifact = analyze(tmp_path, {
        "src/app/__init__.py": "",
        "src/app/a.py": "from app import b\n",
        "src/app/b.py": "from app import a\n",
    })
    findings = build_artifact_report(asdict(artifact))["findings"]
    assert len(findings) == 1
    assert findings[0]["type"] == "circular_dependency"
