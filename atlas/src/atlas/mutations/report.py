"""On-demand projection of either fresh or saved report candidates; no storage."""

from pathlib import Path
from typing import Any

from atlas.domain.mutation_candidates import MutationCandidate

from .config import MutationConfig
from .manifests import generate_manifests


def build_mutation_report(root: Path, report: dict[str, Any], config: MutationConfig) -> dict[str, Any]:
    """Project report candidates into a JSON-ready, schema-versioned manifest list.

    Read current sources to verify every candidate; do not save or apply edits.
    Missing candidate data, validation errors, and generation failures propagate.
    """
    candidates = [MutationCandidate.model_validate(item) for item in report["mutationCandidates"]]
    manifests = generate_manifests(root, candidates, config.rules)
    return {
        "schemaVersion": 1,
        "mutations": [manifest.model_dump(mode="json") for manifest in manifests],
    }
