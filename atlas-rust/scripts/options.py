"""Bounded developer commands. No option weakens parity expectations."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from cases import Case, analysis_cases, navigation_cases, usage_cases
from common import LANGUAGES, REPO, SAMPLES


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Strict CLI parity and subprocess benchmarks; Python is reference, never a runtime dependency.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    result.add_argument("--sample", action="append", choices=LANGUAGES, help="Repeat to select coffee samples; default: all unless projects are selected")
    result.add_argument("--project", action="append", type=Path, help="Read-only project root; repeatable")
    result.add_argument("--projects-dir", type=Path, help="Benchmark immediate project directories, e.g. ~/workspace/projects")
    result.add_argument("--max-projects", type=int, help="Bound sorted project enumeration")
    result.add_argument("--actions", action="append", default=[], help="Repeatable case-name glob, e.g. 'report.*', 'graph.source.*', 'migrate.*'")
    result.add_argument("--max-cases", type=int, help="Bound matching cases per project, including interop and variants")
    result.add_argument("--warmups", type=int, default=1)
    result.add_argument("--repetitions", type=int, default=3)
    result.add_argument("--timeout", type=float, default=120, help="Seconds per subprocess; timeouts fail parity and do not stop later cases")
    result.add_argument("--rust-bin", type=Path, default=REPO / "atlas-rust/target/release/atlas")
    result.add_argument("--rust-migrate", type=Path, default=REPO / "atlas-rust/target/release/atlas-migrate")
    result.add_argument("--output", type=Path, help="New run directory outside all source projects; default: /tmp")
    result.add_argument("--list-actions", action="store_true", help="List selected cases without running implementations")
    result.add_argument("--variants", action="store_true", help="Also test isolated mutation/config/stale-source sample variants")
    result.add_argument("--inventory", type=Path, help="Attach a precomputed language/file inventory JSON")
    return result


def project_roots(args) -> list[Path]:
    roots = [path.expanduser().resolve() for path in args.project or []]
    if args.projects_dir:
        roots.extend(sorted(path.resolve() for path in args.projects_dir.expanduser().iterdir() if path.is_dir()))
    return roots[:args.max_projects]


def projects(args) -> list[Path]:
    roots = project_roots(args)
    samples = args.sample or ([] if roots else list(LANGUAGES))
    return list(dict.fromkeys([*(SAMPLES / language for language in samples), *roots]))


def validate_bounds(args) -> None:
    if args.warmups < 0 or args.repetitions < 1 or args.timeout <= 0:
        parser().error("warmups >= 0, repetitions >= 1, timeout > 0 required")
    if any(value is not None and value < 1 for value in (args.max_projects, args.max_cases)):
        parser().error("project and case bounds must be positive")


def validate_paths(args, roots: list[Path]) -> None:
    if not roots:
        parser().error("No projects selected")
    args.rust_bin, args.rust_migrate = args.rust_bin.resolve(), args.rust_migrate.resolve()
    if not args.rust_bin.is_file():
        parser().error(f"Build the native binary first: {args.rust_bin}")
    args.output = (args.output or Path(tempfile.mkdtemp(prefix="atlas-parity-results-"))).resolve()
    if any(args.output == root or root in args.output.parents for root in roots):
        parser().error("Output must be outside all analyzed projects")
    prepare_output(args)


def prepare_output(args) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "metadata.json").exists():
        parser().error("Output already contains a run; choose a new directory")
    if args.inventory:
        args.inventory = args.inventory.expanduser().resolve()
        json.loads(args.inventory.read_text())


def optional_cases(args, root: Path) -> list[Case]:
    result = []
    if root.parent == SAMPLES:
        from navigation import labels
        result.extend(Case("navigation." + label, ()) for label in labels(root))
    if args.variants:
        from variants import definitions, variant_cases
        for name, _, change in definitions():
            result.extend(variant_cases(name, root, change))
    return result


def available_cases(args) -> list[Case]:
    roots = projects(args)
    root = roots[0] if roots else SAMPLES / "python"
    return (analysis_cases(root) + navigation_cases(root, ("ROOT", "FILE", "FROM", "TO"), "REVISION") +
            usage_cases() + optional_cases(args, root))
