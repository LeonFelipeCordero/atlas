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


@click.group("mutations", invoke_without_command=True, help=(
    "Derive independent JSON byte-edit manifests, never change source or save results. "
    "Opt in via atlas.json: mutations.rules is a list of rule IDs. "
    "Default/empty lists generate nothing. --rules lists exact language coverage. "
    "Conditions, unary operators and unlisted aliases are excluded. Syntactic support is not type validity."
))
@click.option("-f", "--f", "--folder", "folder", default=".", show_default=True, type=click.Path(path_type=Path))
@click.option("--saved", is_flag=True, help="Read persisted candidates for this folder; reject stale sources instead of refreshing")
@click.option("--rules", "show_rules", is_flag=True, help="Show the versioned rule catalog and limitations instead of generating")
def mutations_command(folder: Path, saved: bool, show_rules: bool) -> None:
    """Print the rule catalog or configured independent mutation manifests as JSON.

    Read fresh sources by default; saved mode verifies persisted candidates
    against current sources. Never apply edits, run mutants, or save a graph.
    """
    from atlas.metrics.report import build_artifact_report
    from atlas.services.repositories import analyze_folder

    ctx = click.get_current_context()
    ctx.obj = {"folder": folder, "saved": saved}
    if ctx.invoked_subcommand is not None:
        if show_rules:
            raise click.UsageError("--rules cannot be combined with a subcommand")
        return
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


@mutations_command.command("run", help=(
    "Apply independent mutations and run trusted configured test commands in this workspace. "
    "No baseline or isolation is provided. Nonzero command exits count as killed. "
    "Results are incremental JSONL with separate command logs. Existing results are never overwritten."
))
@click.option("-f", "--folder", type=click.Path(path_type=Path), help="Override the parent project folder")
@click.option("--output", default="mutation-results.jsonl", show_default=True, type=click.Path(path_type=Path),
              help="New results file, relative to the project root")
@click.pass_context
def run_command(ctx: click.Context, folder: Path | None, output: Path) -> None:
    from atlas.metrics.report import build_artifact_report
    from atlas.mutations.manifests import MutationManifest
    from atlas.mutations.runner import MutationRunner
    from atlas.services.repositories import analyze_folder

    try:
        root = (folder or ctx.obj["folder"]).expanduser().resolve()
        config = load_project_config(root).mutations
        if not config.targets:
            raise ValueError("Configure mutations.targets in atlas.json before running mutations")
        report = _saved_report(root) if ctx.obj["saved"] else build_artifact_report(analyze_folder(root))
        planned = build_mutation_report(root, report, config)
        manifests = [MutationManifest.model_validate(item) for item in planned["mutations"]]
        destination = root / output
        counts = MutationRunner(root, config).run(manifests, destination)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps({"output": str(destination.resolve()), "counts": counts}, indent=2))
