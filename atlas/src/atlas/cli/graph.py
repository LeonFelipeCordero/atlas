"""JSON-only read navigation commands; persistence is composed by bootstrap."""

import json
from typing import Any, Callable, get_args

import click

from atlas.bootstrap import navigation_service
from atlas.cli.graph_output import graph_output
from atlas.domain.models import Relationship
from atlas.domain.navigation import NavigationError, PathRequest, Record, TraversalRequest


@click.group("graph", help="Read an indexed graph as JSON; unresolved targets are not classified as external. Stable keys retain their indexed spelling.")
@click.option("--project", help="Registered project name or ID; defaults to the indexed folder containing the current directory.")
@click.option("--revision", help="Expected graphRevision; reject a stale graph.")
@click.pass_context
def graph(ctx: click.Context, project: str | None, revision: str | None) -> None:
    ctx.obj = (project, revision)


class GraphError(click.ClickException):
    """Navigation failures are machine-readable JSON on stderr."""

    def show(self, file: Any = None) -> None:
        click.echo(json.dumps({"error": self.message}), file=file, err=True)


def emit(ctx: click.Context, command: str, **options: Any) -> None:
    project, revision = ctx.obj
    try:
        with navigation_service(project, revision) as service:
            commands: dict[str, Callable[..., Record]] = {
                "overview": service.overview, "find": service.find, "show": service.show,
                "children": service.children, "context": service.context,
                "source": service.source, "path": service.path,
            }
            payload = commands[command](**command_options(command, options))
    except (NavigationError, OSError, ValueError) as error:
        raise GraphError(str(error)) from error
    click.echo(json.dumps(graph_output(payload), ensure_ascii=False))


def command_options(command: str, options: Record) -> Record:
    if command == "context":
        return {"request": TraversalRequest(**options)}
    if command == "path":
        start, target, depth = options.pop("start"), options.pop("target"), options.pop("max_depth")
        return {"request": PathRequest(target, TraversalRequest(key=start, depth=depth, **options))}
    return options


@graph.command("overview")
@click.pass_context
def overview(ctx: click.Context) -> None:
    emit(ctx, "overview")


@graph.command("find")
@click.argument("query")
@click.option("--limit", default=10, show_default=True, type=click.IntRange(1, 100))
@click.pass_context
def find(ctx: click.Context, query: str, limit: int) -> None:
    emit(ctx, "find", query=query, limit=limit)


@graph.command("show")
@click.argument("key")
@click.pass_context
def show(ctx: click.Context, key: str) -> None:
    emit(ctx, "show", key=key)


@graph.command("children")
@click.argument("key")
@click.option("--limit", default=30, show_default=True, type=click.IntRange(1, 100))
@click.option("--offset", default=0, show_default=True, type=click.IntRange(0))
@click.pass_context
def children(ctx: click.Context, **options: Any) -> None:
    emit(ctx, "children", **options)


def relation_list(_ctx: click.Context, _param: click.Parameter, value: str) -> list[str]:
    relations = sorted({part.strip().upper() for part in value.split(",") if part.strip()})
    allowed = get_args(Relationship)
    if not relations or any(relation not in allowed for relation in relations):
        raise click.BadParameter(f"Choose comma-separated relations from {', '.join(allowed)}")
    return relations


def traversal_options(function: Any) -> Any:
    function = click.option("--direction", type=click.Choice(["out", "in", "both"]), default="out", show_default=True)(function)
    function = click.option("--relations", default="CALLS,REFERENCES", show_default=True, callback=relation_list)(function)
    function = click.option("--max-nodes", default=30, show_default=True, type=click.IntRange(1, 300))(function)
    return click.option("--max-edges", default=100, show_default=True, type=click.IntRange(1, 1000))(function)


@graph.command("context")
@click.argument("key")
@click.option("--depth", default=2, show_default=True, type=click.IntRange(0, 20))
@traversal_options
@click.pass_context
def context(ctx: click.Context, **options: Any) -> None:
    emit(ctx, "context", **options)


@graph.command("source")
@click.argument("key")
@click.option("--max-lines", default=80, show_default=True, type=click.IntRange(1, 500))
@click.option("--start-line", type=click.IntRange(1), help="Absolute 1-based line; clamped to the symbol start.")
@click.pass_context
def source(ctx: click.Context, **options: Any) -> None:
    emit(ctx, "source", **options)


@graph.command("path")
@click.argument("start", metavar="FROM")
@click.argument("target", metavar="TO")
@click.option("--max-depth", default=6, show_default=True, type=click.IntRange(0, 20))
@traversal_options
@click.pass_context
def path(ctx: click.Context, **options: Any) -> None:
    emit(ctx, "path", **options)
