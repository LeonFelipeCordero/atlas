"""Keep this repository's explicit target map complete and granular."""

from pathlib import Path

from atlas.metrics.config import load_project_config
from atlas.mutations.runner import matching_targets


def test_project_targets_cover_atlas_production_only():
    root = Path(__file__).resolve().parents[3]
    config = load_project_config(root).mutations
    for source in (root / "atlas/src/atlas").rglob("*.py"):
        assert matching_targets(source.relative_to(root).as_posix(), config), source
    assert list(matching_targets("atlas/src/atlas/metrics/complexity.py", config)) == ["complexity"]
    assert list(matching_targets("atlas/src/atlas/cli/mutations.py", config)) == ["cli-mutations"]
    assert list(matching_targets("atlas/src/atlas/mutations/runner.py", config)) == ["mutations"]
    assert not matching_targets("dashboard/src/routes/index.tsx", config)
    assert not matching_targets("atlas/tests/mutations/test_runner.py", config)
    for target in config.targets.values():
        _assert_command(root, target)


def _assert_command(root, target):
    assert target.command[:3] == ["uv", "run", "pytest"]
    assert all((root / target.cwd / path).exists() for path in target.command[3:])
