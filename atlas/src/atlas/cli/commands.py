"""Command-line entry points for projects, indexing, reports and migration."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from ..domain.repositories import GraphDTO


@click.group(help="Analyze repositories and store their graphs in SQLite")
@click.option("--project", metavar="NAME", help="Unique registered project name (saved reports only)")
@click.option("--database", type=click.Path(path_type=Path), help="SQLite database path")
def main(project: str | None, database: Path | None) -> None:
    pass


def _project(context: click.Context, project: str | None) -> str:
    reference = project if project is not None else context.find_root().params["project"]
    if reference is None:
        raise click.UsageError("Missing option '--project'.", context)
    return reference


def _database(context: click.Context, database: Path | None) -> Path | None:
    return database if database is not None else context.find_root().params["database"]


@main.command("migrate", help="Apply database migrations")
@click.option("--database", type=click.Path(path_type=Path), help="SQLite database path")
@click.pass_context
def migrate_command(context: click.Context, database: Path | None) -> None:
    from ..bootstrap import migrate_database
    from ..domain.repositories import RepositoryError

    try:
        migrate_database(_database(context, database))
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error


@main.command("index", help="Analyze a folder and create or update its saved project graph")
@click.option("-f", "--f", "--folder", "folder", required=True, type=click.Path(path_type=Path), help="Folder to index; use ./ for the current directory")
@click.option("--database", type=click.Path(path_type=Path), help="SQLite database path")
@click.pass_context
def index_command(context: click.Context, folder: Path, database: Path | None) -> None:
    from ..domain.repositories import RepositoryError
    from ..services.repositories import analyze_folder

    if context.find_root().params["project"] is not None:
        raise click.UsageError("'--project' is only supported for saved reports; index selects a folder with '-f'.", context)
    try:
        root = folder.expanduser().resolve()
        artifact = analyze_folder(root)
        saved = _save_folder(root, artifact, _database(context, database))
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps({
        "repositoryId": saved.repositoryId,
        "schemaVersion": saved.artifact["schemaVersion"],
        "stats": saved.artifact["stats"],
    }))


@main.command("projects", help="List all registered projects as JSON")
@click.option("--database", type=click.Path(path_type=Path), help="SQLite database path")
@click.pass_context
def projects_command(context: click.Context, database: Path | None) -> None:
    from ..bootstrap import repository_service
    from ..domain.repositories import RepositoryError

    try:
        with repository_service(_database(context, database)) as service:
            projects = [project.model_dump(mode="json") for project in service.list()]
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(projects, ensure_ascii=False, indent=2))


def _save_folder(root: Path, artifact: dict[str, Any], database: Path | None) -> "GraphDTO":
    from ..bootstrap import migrate_database, repository_service

    migrate_database(database)
    with repository_service(database) as service:
        return service.save_folder(root, artifact)


def _folder_report(folder: Path, database: Path | None, skip_save: bool) -> dict[str, Any]:
    from ..domain.report import build_artifact_report
    from ..services.repositories import analyze_folder

    root = folder.expanduser().resolve()
    artifact = analyze_folder(root)
    report = build_artifact_report(artifact)
    if not skip_save:
        _save_folder(root, artifact, database)
    return report


def _validate_report_source(
    context: click.Context, folder: Path | None, project: str | None, skip_save: bool
) -> None:
    reference = project if project is not None else context.find_root().params["project"]
    if folder is None and reference is None:
        raise click.UsageError("Provide either '--folder' (-f) or '--project' (-p).", context)
    if folder is not None and reference is not None:
        raise click.UsageError("Use either '--folder' or '--project', not both.", context)
    if skip_save and folder is None:
        raise click.UsageError("'--skip-save' requires '--folder'.", context)


@main.command("report", help="Analyze a folder or show saved findings as Markdown or JSON")
@click.option("-f", "--f", "--folder", "folder", type=click.Path(path_type=Path), help="Folder to analyze and save")
@click.option("-p", "--p", "--project", "project", metavar="NAME", help="Unique registered project name (saved results only)")
@click.option("--skip-save", is_flag=True, help="Analyze a folder without accessing the database")
@click.option("--database", type=click.Path(path_type=Path), help="SQLite database path")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True)
@click.pass_context
def report_command(
    context: click.Context, folder: Path | None, project: str | None,
    skip_save: bool, database: Path | None, output_format: str
) -> None:
    from ..domain.report import render_markdown
    from ..domain.repositories import RepositoryError

    _validate_report_source(context, folder, project, skip_save)
    try:
        if folder is not None:
            report = _folder_report(folder, _database(context, database), skip_save)
        else:
            from ..bootstrap import repository_service

            with repository_service(_database(context, database)) as service:
                report = service.report(_project(context, project))
    except (OSError, ValueError, RuntimeError, RepositoryError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(report, ensure_ascii=False, indent=2) if output_format == "json" else render_markdown(report))


if __name__ == "__main__":
    main()
