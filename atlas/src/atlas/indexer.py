"""Analyze repositories into in-memory graph artifacts."""

from pathlib import Path

from .parsing.discovery import discover_files, validate_repository
from .metrics.artifact import GraphArtifact, build_artifact
from .metrics.callables import add_callable_metrics
from .metrics.resolver import resolve_connections
from .parsing.parser import parse_files


def analyze_repository(root: Path) -> GraphArtifact:
    """Build a repository graph without writing an output file.

    Args:
        root: Repository directory, relative or absolute; Git is not required.
    Returns:
        Validated graph artifact with metadata, relationships, and diagnostics.
    Raises:
        ValueError: Root is not a directory or graph/model validation fails.
        OSError: Repository path resolution or file reading fails.
        UnicodeError: An ignore file cannot be decoded.
        RuntimeError: Path resolution encounters a symlink loop on Python 3.10–3.12.

    Example:
        artifact = analyze_repository(Path("."))
        print(artifact.stats)
    """
    repository_root = validate_repository(root)
    parsed_repository = parse_files(discover_files(repository_root))
    add_callable_metrics(parsed_repository)
    graph = resolve_connections(parsed_repository)
    return build_artifact(repository_root, parsed_repository, graph)
