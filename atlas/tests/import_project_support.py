"""Whole coffee projects with small, source-visible domain overlays."""

from pathlib import Path

from atlas.indexer import analyze_repository
from atlas.metrics.artifact import GraphArtifact
from atlas.metrics.resolver import resolve_connections
from atlas.parsing.discovery import SourceFile, detect_language
from atlas.parsing.parser import parse_files
from tests.coffee_fixture import coffee_sources

VARIANTS = Path(__file__).parent / "fixtures/variants"


def project_sources(language: str, variant: str | None = None) -> dict[str, str]:
    sources = {source.path: source.source.decode() for source in coffee_sources(language)}
    if variant:
        root = VARIANTS / language / variant
        assert root.is_dir(), root
        sources.update({path.relative_to(root).as_posix(): path.read_text()
                        for path in sorted(root.rglob("*")) if path.is_file()})
    return sources


def repository(language: str, sources: dict[str, str]):
    return parse_files([
        SourceFile(path, Path("/coffee") / path, grammar, text.encode())
        for path, text in sources.items()
        if (grammar := detect_language(Path(path))) and grammar not in {"gomod", "toml"}
    ])


def project_repository(language: str, variant: str | None = None):
    return repository(language, project_sources(language, variant))


def analyze(root: Path, sources: dict[str, str]) -> GraphArtifact:
    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return analyze_repository(root)


def symbols(repo, path: str, name: str):
    file = next(file for file in repo.files if file.source.path == path)
    matches = [symbol for symbol in file.symbols if symbol.qualified_name == f"{path}::{name}"]
    assert matches, (path, name)
    return matches


def connections_at(repo, site: tuple[str, str], relationship: str):
    path, evidence = site
    file = next(file for file in repo.files if file.source.path == path)
    assert evidence in file.source.source.decode(), site
    edges = [edge for edge in resolve_connections(repo).connections
             if edge.type == relationship and edge.path == path and edge.evidence == evidence]
    assert edges, (*site, relationship)
    return edges


def edges_at(repo, path: str, evidence: str):
    return connections_at(repo, (path, evidence), "CALLS")


def imports_at(repo, path: str, evidence: str):
    return connections_at(repo, (path, evidence), "IMPORTS")


def assert_call(repo, site: tuple[str, str], target: tuple[str, str]):
    edges = edges_at(repo, *site)
    targets = {symbol.key for symbol in symbols(repo, *target)}
    assert len(edges) == len(targets), (site, target, edges)
    assert {edge.target_key for edge in edges} == targets
    return edges


def assert_external(repo, path: str, evidence: str):
    edges = edges_at(repo, path, evidence)
    assert all(edge.target_key.startswith("external:") for edge in edges)
    return edges
