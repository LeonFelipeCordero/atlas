#!/usr/bin/env python3
"""Strict CLI parity and subprocess benchmarks. Run --help for bounded iteration."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from options import available_cases, parser, projects, validate_bounds, validate_paths
from project import Project
from reporting import metadata, write_report
from session import Run


def run_project(run: Run, root: Path) -> None:
    run.case_count = 0
    try:
        with tempfile.TemporaryDirectory(prefix="atlas-parity-work-") as temporary:
            Project(run, root, Path(temporary)).execute()
    except (OSError, ValueError, RuntimeError, AssertionError, sqlite3.Error) as error:
        run.save({"project": str(root), "case": "harness", "passed": False, "error": str(error)})
        print(f"FAIL {root}: {error}", file=sys.stderr)


def main() -> int:
    sys.dont_write_bytecode = True
    args = parser().parse_args()
    validate_bounds(args)
    run = Run(args)
    if args.list_actions:
        for case in filter(run.selected, available_cases(args)):
            print(case.name, *case.args)
        return 0
    roots = projects(args)
    validate_paths(args, roots)
    (args.output / "metadata.json").write_text(json.dumps(metadata(args), default=str, indent=2) + "\n")
    for root in roots:
        run_project(run, root)
    passed = write_report(run)
    print(f"Results: {args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
