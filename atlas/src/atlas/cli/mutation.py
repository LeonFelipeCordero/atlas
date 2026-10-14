"""Mutation planning, externally reported evidence, and resumable ledger reports."""

import json
from pathlib import Path
from typing import Any

import click

from atlas.bootstrap import mutation_service
from atlas.domain.mutation import MutationTrialInput
from atlas.domain.repositories import RepositoryError
from atlas.mutation.reporting import render_mutation_markdown


@click.group(help="Discover mutation opportunities and store agent-reported experiments; never edits source or runs tests")
def mutation() -> None:
    pass


def _output(report: dict[str, Any], output_format: str) -> None:
    click.echo(json.dumps(report, ensure_ascii=False, indent=2) if output_format == "json" else render_mutation_markdown(report))


@mutation.command("plan", help="Persist a fresh source/site snapshot; requires an explicitly migrated Atlas database")
@click.option("-f", "--f", "--folder", "folders", multiple=True, type=click.Path(path_type=Path), help="Folder scope; repeatable, defaults to .")
@click.option("--base", help="Compare this Git revision directly with captured working-tree source, including untracked files")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="json", show_default=True)
def plan_command(folders: tuple[Path, ...], base: str | None, output_format: str) -> None:
    try:
        with mutation_service() as service:
            report = service.plan(folders, base)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    _output(report, output_format)


@mutation.command("record", help="Append a version-1 agent-reported trial; matching source hashes do not verify execution")
@click.option("--session", "session_id", required=True)
@click.option("--site", "site_id", required=True)
@click.option("--result", "result_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def record_command(session_id: str, site_id: str, result_path: Path) -> None:
    try:
        result = MutationTrialInput.model_validate_json(result_path.read_bytes())
        with mutation_service() as service:
            acknowledgement = service.record(session_id, site_id, result)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(acknowledgement, ensure_ascii=False, indent=2))


@mutation.command("report", help="Resume a persisted session and inspect evidence and current source status")
@click.option("--session", "session_id", required=True)
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True)
def report_command(session_id: str, output_format: str) -> None:
    try:
        with mutation_service() as service:
            report = service.report(session_id)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    _output(report, output_format)
