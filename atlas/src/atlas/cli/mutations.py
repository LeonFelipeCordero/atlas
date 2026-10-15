"""Inspect derived mutation manifests without applying or persisting edits."""

import json
from pathlib import Path
from typing import Any

import click

from atlas.domain.repositories import RepositoryError
from atlas.metrics.config import load_project_config
from atlas.mutations.report import build_mutation_report
from atlas.mutations.rules import REGISTRY


def _saved_report(root: Path) -> dict[str, Any]:
    from atlas.bootstrap import repository_service

    with repository_service() as service:
        projects = [project for project in service.list()
                    if "://" not in project.location and Path(project.location).expanduser().resolve() == root]
        if len(projects) != 1:
            raise ValueError("Expected one indexed project at this folder; run atlas index first")
        return service.report(projects[0].name)


@click.command("mutations", help=(
    "Derive independent JSON byte-edit manifests, never change source or save results. "
    "Opt in via atlas.json: mutations.rules is a list of rule IDs. "
    "Default/empty lists generate nothing. --rules lists exact language coverage. "
    "Conditions, unary operators and unlisted aliases are excluded. Syntactic support is not type validity."
))
@click.option("-f", "--f", "--folder", "folder", default=".", show_default=True, type=click.Path(path_type=Path))
@click.option("--saved", is_flag=True, help="Read persisted candidates for this folder; reject stale sources instead of refreshing")
@click.option("--rules", "show_rules", is_flag=True, help="Show the versioned rule catalog and limitations instead of generating")
def mutations_command(folder: Path, saved: bool, show_rules: bool) -> None:
    from atlas.metrics.report import build_artifact_report
    from atlas.services.repositories import analyze_folder

    try:
        if show_rules:
            result = {"rules": [rule.model_dump(mode="json") for rule in REGISTRY]}
        else:
            root = folder.expanduser().resolve()
            config = load_project_config(root).mutations
            report = _saved_report(root) if saved else build_artifact_report(analyze_folder(root))
            result = build_mutation_report(root, report, config)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(result, ensure_ascii=False, indent=2))
