"""Python project layouts must produce local dependencies, not external guesses."""

from tests.import_snapshot_support import import_case_sources as case_sources

from dataclasses import asdict
from pathlib import Path

import pytest

from atlas.metrics.report import build_artifact_report
from atlas.indexer import analyze_repository


def analyze(root: Path, sources: dict[str, str]):
    for path, source in sources.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    return analyze_repository(root)


@pytest.mark.parametrize('case_id,prefix,relationship', [('python-project-imports-package-imports-resolve-independently-of-analysis-root-1', '', 'IMPORTS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-1', '', 'CALLS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-1', '', 'INHERITS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-4', 'src/', 'IMPORTS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-4', 'src/', 'CALLS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-4', 'src/', 'INHERITS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-7', 'services/backend/', 'IMPORTS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-7', 'services/backend/', 'CALLS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-7', 'services/backend/', 'INHERITS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-10', 'services/backend/src/', 'IMPORTS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-10', 'services/backend/src/', 'CALLS'), ('python-project-imports-package-imports-resolve-independently-of-analysis-root-10', 'services/backend/src/', 'INHERITS')])
def test_package_imports_resolve_independently_of_analysis_root(tmp_path, case_id, prefix, relationship):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    edges = [edge for edge in artifact.edges if edge["type"] == relationship]
    assert edges
    assert all(prefix + "app/worker.py" in edge["targetStableKey"] for edge in edges)
    assert build_artifact_report(asdict(artifact))["summary"]["circularImportGroups"] == 0


def test_src_namespace_package(tmp_path):
    artifact = analyze(tmp_path, case_sources("imports", "python-project-imports-src-namespace-package"))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize(('case_id',), [('python-project-imports-child-module-imports-link-and-bind-namespace-1',), ('python-project-imports-child-module-imports-link-and-bind-namespace-2',), ('python-project-imports-child-module-imports-link-and-bind-namespace-3',)])
def test_child_module_imports_link_and_bind_namespace(tmp_path, case_id):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


def test_comma_separated_module_imports(tmp_path):
    artifact = analyze(tmp_path, case_sources("imports", "python-project-imports-comma-separated-module-imports"))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 4
    assert all(not edge["targetStableKey"].startswith("external:") for edge in edges)


def test_duplicate_source_roots_are_ambiguous(tmp_path):
    artifact = analyze(tmp_path, case_sources("imports", "python-project-imports-duplicate-source-roots-are-ambiguous"))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


def test_unrelated_suffix_is_not_an_import_root(tmp_path):
    artifact = analyze(tmp_path, case_sources("imports", "python-project-imports-unrelated-suffix-is-not-an-import-root"))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


@pytest.mark.parametrize('case_id,module', [('python-project-imports-runtime-modules-take-precedence-over-type-stubs-1', 'app/worker'), ('python-project-imports-runtime-modules-take-precedence-over-type-stubs-2', 'app/worker/__init__')])
def test_runtime_modules_take_precedence_over_type_stubs(tmp_path, case_id, module):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/" + module + ".py" in edge["targetStableKey"] for edge in edges)
    assert all(".pyi" not in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize(('case_id',), [('python-project-imports-package-attributes-prevent-child-module-guesses-1',), ('python-project-imports-package-attributes-prevent-child-module-guesses-2',), ('python-project-imports-package-attributes-prevent-child-module-guesses-3',), ('python-project-imports-package-attributes-prevent-child-module-guesses-4',), ('python-project-imports-package-attributes-prevent-child-module-guesses-5',), ('python-project-imports-package-attributes-prevent-child-module-guesses-6',)])
def test_package_attributes_prevent_child_module_guesses(tmp_path, case_id):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
    assert len(calls) == 1
    assert calls[0]["targetStableKey"].startswith("external:")
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    assert all("app/worker.py" not in edge["targetStableKey"] for edge in imports)


@pytest.mark.parametrize(('case_id',), [('python-project-imports-annotation-only-attribute-does-not-hide-child-module-1',), ('python-project-imports-annotation-only-attribute-does-not-hide-child-module-2',)])
def test_annotation_only_attribute_does_not_hide_child_module(tmp_path, case_id):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all("src/app/worker.py" in edge["targetStableKey"] for edge in edges)


@pytest.mark.parametrize(('case_id',), [('python-project-imports-ambiguous-parent-package-cannot-resolve-unique-child-1',), ('python-project-imports-ambiguous-parent-package-cannot-resolve-unique-child-2',)])
def test_ambiguous_parent_package_cannot_resolve_unique_child(tmp_path, case_id):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    edges = [edge for edge in artifact.edges if edge["type"] in {"IMPORTS", "CALLS"}]
    assert len(edges) == 2
    assert all(edge["targetStableKey"].startswith("external:") for edge in edges)


@pytest.mark.parametrize(('case_id',), [('python-project-imports-ordinary-module-cannot-have-child-modules-1',), ('python-project-imports-ordinary-module-cannot-have-child-modules-2',)])
def test_ordinary_module_cannot_have_child_modules(tmp_path, case_id):
    artifact = analyze(tmp_path, case_sources("imports", case_id))
    calls = [edge for edge in artifact.edges if edge["type"] == "CALLS"]
    assert len(calls) == 1
    assert calls[0]["targetStableKey"].startswith("external:")
    imports = [edge for edge in artifact.edges if edge["type"] == "IMPORTS"]
    assert all("app/worker.py" not in edge["targetStableKey"] for edge in imports)


def test_absolute_src_import_cycle_is_reported(tmp_path):
    artifact = analyze(tmp_path, case_sources("imports", "python-project-imports-absolute-src-import-cycle-is-reported"))
    report = build_artifact_report(asdict(artifact))
    assert report["summary"]["circularImportGroups"] == 1
    assert report["circularImports"][0]["groupSize"] == 2
