"""Whole-shop layouts, package attributes and competing roots resolve conservatively."""

from dataclasses import asdict

import pytest

from atlas.metrics.report import build_artifact_report
from tests.import_project_support import (
    analyze, assert_call, assert_external, imports_at, project_sources, repository, symbols,
)

RECIPE = "src/coffee/brewing/recipe.py"
PROBE = "tasting.py"


def package_sources():
    sources = project_sources("python")
    for package in ("coffee", "coffee/brewing", "coffee/reporting", "coffee/inventory", "coffee/orders"):
        sources[f"src/{package}/__init__.py"] = ""
    return sources


def child_probe(form):
    if form == "relative":
        return "from . import recipe\ndef tasting(): return recipe.portions('espresso')\n"
    if form == "absolute":
        return "from coffee.brewing import recipe\ndef tasting(): return recipe.portions('espresso')\n"
    return "from coffee.brewing import recipe as menu\ndef tasting(): return menu.portions('espresso')\n"


@pytest.mark.parametrize("prefix", ["", "src/", "services/backend/", "services/backend/src/"])
def test_package_imports_resolve_independently_of_analysis_root(tmp_path, prefix):
    sources = {prefix + path.removeprefix("src/"): text for path, text in package_sources().items()}
    path = prefix + "coffee/tasting.py"
    sources[path] = ("from coffee.brewing.brewer import Brewing\n"
                     "from coffee.brewing.recipe import portions\n"
                     "class Tasting(Brewing):\n    def brew(self, names): return portions('espresso')\n")
    artifact = analyze(tmp_path, sources)
    edges = [edge for edge in artifact.edges if edge["path"] == path]
    repo = repository("python", sources)
    targets = {
        "IMPORTS": {"file:" + prefix + "coffee/brewing/brewer.py", "file:" + prefix + "coffee/brewing/recipe.py"},
        "CALLS": {symbol.key for symbol in symbols(repo, prefix + "coffee/brewing/recipe.py", "portions")},
        "INHERITS": {symbol.key for symbol in symbols(repo, prefix + "coffee/brewing/brewer.py", "Brewing")},
    }
    for relationship, expected in targets.items():
        assert_relationship_targets(edges, relationship, expected)
    # Existing coffee cycles remain visible regardless of root layout.
    assert build_artifact_report(asdict(artifact))["summary"]["circularImportGroups"] >= 1


def assert_relationship_targets(edges, relationship, expected):
    assert {edge["targetStableKey"] for edge in edges if edge["type"] == relationship} == expected


@pytest.mark.parametrize("packaged", [False, True])
@pytest.mark.parametrize("form", ["relative", "absolute", "alias"])
def test_child_module_imports_link_and_bind_namespace(packaged, form):
    sources = package_sources() if packaged else project_sources("python")
    path = "src/coffee/brewing/" + PROBE
    sources[path] = child_probe(form)
    repo = repository("python", sources)
    evidence = "from . import recipe" if form == "relative" else "from coffee.brewing import recipe"
    if form == "alias":
        evidence += " as menu"
    assert {edge.target_key for edge in imports_at(repo, path, evidence)} == {"file:" + RECIPE}
    assert_call(repo, (path, ("menu" if form == "alias" else "recipe") + ".portions('espresso')"), (RECIPE, "portions"))


def test_comma_separated_module_imports():
    sources = package_sources()
    path = "src/coffee/" + PROBE
    evidence = "import coffee.brewing.recipe as menu, coffee.reporting.report as receipt"
    sources[path] = evidence + "\ndef tasting():\n    menu.portions('espresso')\n    return receipt.render(['espresso'])\n"
    repo = repository("python", sources)
    assert {edge.target_key for edge in imports_at(repo, path, evidence)} == {
        "file:" + RECIPE, "file:src/coffee/reporting/report.py",
    }
    assert_call(repo, (path, "menu.portions('espresso')"), (RECIPE, "portions"))
    assert_call(repo, (path, "receipt.render(['espresso'])"), ("src/coffee/reporting/report.py", "render"))


@pytest.mark.parametrize("form", ["absolute", "alias"])
def test_duplicate_source_roots_and_ambiguous_parent_cannot_choose_child(form):
    sources = package_sources()
    # Both packages exist, but the second has no recipe child. A unique child
    # cannot rescue an ambiguous parent namespace.
    sources["services/backend/src/coffee/__init__.py"] = ""
    sources["services/backend/src/coffee/brewing/__init__.py"] = ""
    sources[PROBE] = child_probe(form)
    repo = repository("python", sources)
    assert_external(repo, PROBE, ("menu" if form == "alias" else "recipe") + ".portions('espresso')")
    imports = imports_at(repo, PROBE, "from coffee.brewing import recipe" + (" as menu" if form == "alias" else ""))
    assert all(edge.target_key.startswith("external:") for edge in imports)


def test_duplicate_complete_source_roots_are_ambiguous():
    sources = package_sources()
    sources.update({"services/backend/" + path: text for path, text in list(sources.items())})
    sources[PROBE] = "from coffee.brewing.recipe import portions\ndef tasting(): return portions('espresso')\n"
    repo = repository("python", sources)
    assert_external(repo, PROBE, "portions('espresso')")
    assert all(edge.target_key.startswith("external:") for edge in imports_at(repo, PROBE, "from coffee.brewing.recipe import portions"))


def test_unrelated_suffix_is_not_an_import_root():
    sources = project_sources("python")
    sources["examples/roast.py"] = "def portions(name): return 2\n"
    sources[PROBE] = "import roast\ndef tasting(): return roast.portions('espresso')\n"
    repo = repository("python", sources)
    assert_external(repo, PROBE, "roast.portions('espresso')")
    assert all(edge.target_key.startswith("external:") for edge in imports_at(repo, PROBE, "import roast"))


@pytest.mark.parametrize("package", [False, True])
def test_runtime_modules_take_precedence_over_type_stubs(package):
    sources = package_sources()
    runtime = RECIPE if not package else "src/coffee/brewing/recipe/__init__.py"
    if package:
        sources[runtime] = sources.pop(RECIPE)
    stub = runtime.removesuffix(".py") + ".pyi"
    sources[stub] = "def portions(name: str) -> int: ...\n"
    sources[PROBE] = child_probe("absolute")
    repo = repository("python", sources)
    assert_call(repo, (PROBE, "recipe.portions('espresso')"), (runtime, "portions"))
    assert {edge.target_key for edge in imports_at(repo, PROBE, "from coffee.brewing import recipe")} == {"file:" + runtime}


@pytest.mark.parametrize("binding", ["recipe = None", "from coffee.reporting import report as recipe", "import sys as recipe"])
@pytest.mark.parametrize("form", ["absolute", "alias"])
def test_package_attributes_prevent_child_module_guesses(binding, form):
    sources = package_sources()
    sources["src/coffee/brewing/__init__.py"] = binding + "\n"
    sources[PROBE] = child_probe(form)
    repo = repository("python", sources)
    assert_external(repo, PROBE, ("menu" if form == "alias" else "recipe") + ".portions('espresso')")
    imports = imports_at(repo, PROBE, "from coffee.brewing import recipe" + (" as menu" if form == "alias" else ""))
    assert all(edge.target_key != "file:" + RECIPE for edge in imports)


@pytest.mark.parametrize("form", ["absolute", "alias"])
def test_annotation_only_attribute_does_not_hide_child_module(form):
    sources = package_sources()
    sources["src/coffee/brewing/__init__.py"] = "recipe: object\n"
    sources[PROBE] = child_probe(form)
    repo = repository("python", sources)
    assert_call(repo, (PROBE, ("menu" if form == "alias" else "recipe") + ".portions('espresso')"), (RECIPE, "portions"))


@pytest.mark.parametrize("form", ["absolute", "alias"])
def test_ordinary_module_cannot_have_child_modules(form):
    sources = project_sources("python")
    sources["src/coffee/brewing.py"] = ""
    sources[PROBE] = child_probe(form)
    repo = repository("python", sources)
    assert_external(repo, PROBE, ("menu" if form == "alias" else "recipe") + ".portions('espresso')")
    assert all(edge.target_key != "file:" + RECIPE for edge in imports_at(repo, PROBE, "from coffee.brewing import recipe" + (" as menu" if form == "alias" else "")))


def test_absolute_src_import_cycle_is_reported(tmp_path):
    sources = project_sources("python")
    sources["src/coffee/dispatch.py"] = "from coffee import delivery\n"
    sources["src/coffee/delivery.py"] = "from coffee import dispatch\n"
    artifact = analyze(tmp_path, sources)
    assert artifact.circularDependencies is not None
    assert any(group["nodeStableKeys"] == ["file:src/coffee/delivery.py", "file:src/coffee/dispatch.py"]
               for group in artifact.circularDependencies["groups"])
