"""Index local coffee samples through the production repository pipeline."""
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlas.metrics.artifact import GraphArtifact
from atlas.parsing.discovery import discover_files
from atlas.indexer import analyze_repository

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/coffee"
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"
LANGUAGES = (
    "java",
    "kotlin",
    "go",
    "rust",
    "javascript",
    "typescript",
    "elixir",
    "python",
)


def coffee_sources(language: str):
    if language not in LANGUAGES:
        raise ValueError(f"Unknown coffee language: {language}")
    return [
        source for source in discover_files(FIXTURE_ROOT / language)
        if source.language == language
    ]


def coffee_graph(language: str) -> GraphArtifact:
    return analyze_repository(FIXTURE_ROOT / language)


def coffee_snapshot(artifact: GraphArtifact) -> dict[str, Any]:
    """Normalize checkout paths and timestamp only, without changing the artifact."""
    snapshot = asdict(artifact)
    del snapshot["repository"]["indexedAt"]
    root = f"/samples/coffee/{snapshot['repository']['name']}"
    snapshot["repository"]["path"] = root
    snapshot["nodes"][0]["properties"]["absolutePath"] = root
    return snapshot
