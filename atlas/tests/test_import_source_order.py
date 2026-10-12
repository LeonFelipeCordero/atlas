"""Input ordering must neither select ambiguous targets nor lose project files."""

from dataclasses import asdict
from pathlib import Path
from random import Random

import pytest

from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import detect_language
from tests.coffee_fixture import LANGUAGES
from tests.import_project_support import assert_external, project_sources, repository


def facts(repo):
    add_callable_metrics(repo)
    graph = resolve_connections(repo)
    return {
        "connections": {repr(asdict(edge)) for edge in graph.connections},
        "externals": {repr(asdict(node)) for node in graph.external_nodes},
        "symbols": {repr(asdict(symbol)) for file in repo.files for symbol in file.symbols},
    }


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("order", ["reversed", "shuffled"])
def test_whole_project_resolution_is_independent_of_source_order(language, order):
    sources = {path: text for path, text in project_sources(language).items()
               if detect_language(Path(path)) not in {None, "gomod", "toml"}}
    paths = list(sources)
    if order == "reversed":
        paths.reverse()
    else:
        Random(18).shuffle(paths)
    reordered = {path: sources[path] for path in paths}
    repo = repository(language, reordered)
    assert [file.source.path for file in repo.files] == paths
    assert {file.source.path: file.source.source.decode() for file in repo.files} == sources
    assert facts(repo) == facts(repository(language, sources))


@pytest.mark.parametrize("order", ["forward", "reversed", "shuffled"])
def test_ambiguous_roast_call_remains_external_in_every_source_order(order):
    sources = project_sources("typescript", "ambiguous-roast-call")
    paths = list(sources)
    if order == "reversed":
        paths.reverse()
    elif order == "shuffled":
        Random(18).shuffle(paths)
    repo = repository("typescript", {path: sources[path] for path in paths})
    assert_external(repo, "brewing/tasting.ts", "roast()")
