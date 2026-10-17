"""Explicit or interactive selection of configured mutation test targets."""

import sys
from contextlib import redirect_stdout

import click

from atlas.mutations.config import MutationConfig, MutationTarget


def _parse_targets(value: str, config: MutationConfig) -> dict[str, MutationTarget]:
    names = [name.strip() for name in value.split(",")]
    if not all(names):
        raise click.BadParameter("Provide comma-separated target names or 'all'; empty names are not allowed", param_hint="--target")
    if names == ["all"]:
        return config.targets
    if "all" in names:
        raise click.BadParameter("Use 'all' alone, not with other target names", param_hint="--target")
    unknown = set(names) - config.targets.keys()
    if unknown:
        raise click.BadParameter(f"Unknown mutation targets: {', '.join(sorted(unknown))}. "
                                 f"Available targets: {', '.join(config.targets)}, all", param_hint="--target")
    return {name: config.targets[name] for name in dict.fromkeys(names)}


def select_targets(config: MutationConfig, value: str | None) -> MutationConfig:
    """Prompt only on a terminal; validate selections before analysis or execution."""
    if value is not None:
        selected = _parse_targets(value, config)
    else:
        if not sys.stdin.isatty():
            raise click.UsageError("Pass --target NAME[,NAME...] or --target all when stdin is not a terminal")
        click.echo("Available mutation targets:", err=True)
        click.echo("  all (all configured targets)", err=True)
        for name in config.targets:
            click.echo(f"  {name}", err=True)
        # Keep prompt/input echo off stdout, which is reserved for the JSON summary.
        with redirect_stdout(sys.stderr):
            selected = click.prompt("Targets (comma-separated names or all)", err=True,
                                    value_proc=lambda text: _parse_targets(text, config))
    return config.model_copy(update={"targets": selected})
