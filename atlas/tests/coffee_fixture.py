"""Index local coffee samples through the production repository pipeline."""
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlas.metrics.artifact import GraphArtifact
from atlas.parsing.discovery import discover_files
from atlas.indexer import analyze_repository

FIXTURE_ROOT = Path(__file__).resolve().parent / "code_samples"
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
    "tsx",
)
BREWING_LANGUAGES = tuple(language for language in LANGUAGES if language != "tsx")
# These physical samples intentionally contain syntax errors.
PARSE_ERROR_PATHS = {
    "javascript": {"edge_cases/cli/syntax-javascript/brewing/Brewer.js"},
    "typescript": {"edge_cases/ambiguous-roast-namespace/inventory/dark.ts"},
    "python": {
        "edge_cases/cli/syntax-python/examples/coffee/brewing/recipe.py",
        "edge_cases/metrics/tracking_malformed.py",
        "edge_cases/parsing/missing-condition-colon/scheduling.py",
        "edge_cases/parsing/missing-parameter-delimiter/scheduling.py",
    },
}


def coffee_sources(language: str):
    if language not in LANGUAGES:
        raise ValueError(f"Unknown coffee language: {language}")
    return list(discover_files(FIXTURE_ROOT / language))


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
