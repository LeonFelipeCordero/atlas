"""Environment records and benchmark summaries. No timing includes database cloning."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from itertools import groupby
from pathlib import Path

from common import REPO


def version(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, cwd=REPO, stderr=subprocess.STDOUT, timeout=10).decode().strip()
    except (OSError, subprocess.SubprocessError) as error:
        return str(error)


def fingerprint(path: Path) -> dict:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}


def cpu_model() -> str:
    try:
        lines = Path("/proc/cpuinfo").read_text().splitlines()
        return next((line.partition(":")[2].strip() for line in lines if line.startswith("model name")), platform.processor())
    except OSError:
        return platform.processor()


def metadata(args) -> dict:
    package_code = "from importlib.metadata import distributions; print('\\n'.join(sorted(f'{d.metadata[\"Name\"]}=={d.version}' for d in distributions())))"
    return {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "argv": sys.argv,
            "options": vars(args).copy(), "platform": platform.platform(), "machine": platform.machine(),
            "cpu_count": os.cpu_count(), "processor": cpu_model(), "python": sys.version,
            "environment": {key: os.environ.get(key) for key in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "UV_PYTHON", "CARGO_BUILD_TARGET", "RUSTFLAGS")},
            "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
            "sqlite": __import__("sqlite3").sqlite_version,
            "git_revision": version(["git", "rev-parse", "HEAD"]), "git_status": version(["git", "status", "--porcelain"]),
            "rustc": version(["rustc", "--version"]), "cargo": version(["cargo", "--version"]),
            "python_packages": version([sys.executable, "-c", package_code]),
            "inputs": [fingerprint(path) for path in (args.rust_bin, args.rust_migrate, REPO / "atlas-rust/Cargo.lock", REPO / "atlas/uv.lock")]}


def timings(values: list[int]) -> dict:
    return {"median_ns": statistics.median(values), "min_ns": min(values), "max_ns": max(values), "samples": len(values)}


def case_summary(rows: list[dict]) -> dict:
    return {"project": rows[0]["project"], "case": rows[0]["case"], "passed": all(row["passed"] for row in rows),
            "python": timings([row["python"]["elapsed_ns"] for row in rows]),
            "rust": timings([row["rust"]["elapsed_ns"] for row in rows])}


def summary(records: list[dict]) -> list[dict]:
    measured = [record for record in records if record.get("phase") == "measured" and "python" in record]
    def key(record):
        return record["project"], record["case"]
    return [case_summary(list(rows)) for _, rows in groupby(sorted(measured, key=key), key)]


def write_report(run) -> bool:
    report = {"passed": bool(run.records) and all(record["passed"] for record in run.records),
              "coverage": run.coverage, "summary": summary(run.records),
              "failures": [record for record in run.records if not record["passed"]]}
    (run.args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    return report["passed"]
