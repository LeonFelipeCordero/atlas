"""Command-line entry points for projects, indexing and reports."""

import json
from pathlib import Path
from typing import Any

import click

from atlas.cli.graph import graph

@click.group(help="Analyze repositories and store their graphs in SQLite")
def main() -> None:
    pass


@main.command("index", help="Analyze a folder and save its graph in SQLite")
@click.option("-f", "--f", "--folder", "folder", default=".", show_default=True, type=click.Path(path_type=Path), help="Folder to index")
def index_command(folder: Path) -> None:
    from ..bootstrap import repository_service
    from ..domain.repositories import RepositoryError
    from ..services.repositories import analyze_folder

    try:
        root = folder.expanduser().resolve()
        artifact = analyze_folder(root)
        with repository_service() as service:
            saved = service.save_folder(root, artifact)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps({
        "repositoryId": saved.repositoryId,
        "schemaVersion": saved.schemaVersion,
        "stats": saved.stats.model_dump(),
    }))


@main.command("projects", help="List all registered projects as JSON")
def projects_command() -> None:
    from ..bootstrap import repository_service
    from ..domain.repositories import RepositoryError

    try:
        with repository_service() as service:
            projects = [project.model_dump(mode="json") for project in service.list()]
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(projects, ensure_ascii=False, indent=2))


def _folder_report(folder: Path, skip_save: bool) -> dict[str, Any]:
    from ..metrics.report import build_artifact_report
    from ..services.repositories import analyze_folder

    root = folder.expanduser().resolve()
    artifact = analyze_folder(root)
    report = build_artifact_report(artifact)
    if not skip_save:
        from ..bootstrap import repository_service

        with repository_service() as service:
            service.save_folder(root, artifact)
    return report


@main.command("report", help="Analyze a folder and show findings as Markdown or JSON")
@click.option("-f", "--f", "--folder", "folder", default=".", show_default=True, type=click.Path(path_type=Path), help="Folder to analyze and save")
@click.option("--skip-save", is_flag=True, help="Analyze a folder without accessing the database")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True)
def report_command(folder: Path, skip_save: bool, output_format: str) -> None:
    from ..metrics.report import render_markdown
    from ..domain.repositories import RepositoryError

    try:
        report = _folder_report(folder, skip_save)
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(report, ensure_ascii=False, indent=2) if output_format == "json" else render_markdown(report))


main.add_command(graph)


if __name__ == "__main__":
    main()
