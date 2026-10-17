"""Sequential execution of trusted test commands against independent byte edits.

No baseline or workspace is created. Callers own test selection and isolation.
"""

import base64
import hashlib
import json
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from fnmatch import fnmatchcase
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from .config import MutationConfig, MutationTarget
from .manifests import MutationManifest


def _matches(parts: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return not parts
    if patterns[0] == "**":
        return _matches(parts, patterns[1:]) or bool(parts) and _matches(parts[1:], patterns)
    return bool(parts) and fnmatchcase(parts[0], patterns[0]) and _matches(parts[1:], patterns[1:])


def matching_targets(path: str, config: MutationConfig) -> dict[str, MutationTarget]:
    """Match rooted POSIX globs: only ** crosses directory separators."""
    return {name: target for name, target in config.targets.items()
            if any(_matches(tuple(path.split("/")), tuple(pattern.split("/"))) for pattern in target.sources)}


def _working_directories(root: Path, config: MutationConfig) -> dict[str, Path]:
    directories = {name: (root / target.cwd).resolve() for name, target in config.targets.items()}
    for name, directory in directories.items():
        if not directory.is_relative_to(root) or not directory.is_dir():
            raise ValueError(f"Invalid working directory for target {name}: {directory}")
    return directories


def _stop(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait()


def _run_command(target: MutationTarget, cwd: Path, log: Path) -> dict:
    started = time.monotonic()
    result: dict = {"command": target.command, "log": str(log), "exitCode": None}
    try:
        with log.open("xb") as stream, TemporaryDirectory(prefix="atlas-pycache-") as cache:
            # Same-size edits in one second can otherwise reuse stale Python bytecode.
            environment = {**os.environ, "PYTHONPYCACHEPREFIX": cache, "PYTHONDONTWRITEBYTECODE": "1"}
            process = subprocess.Popen(target.command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                       env=environment, start_new_session=os.name == "posix")
            try:
                code = process.wait(timeout=target.timeoutSeconds)
                result.update(outcome="survived" if code == 0 else "killed", exitCode=code)
            except subprocess.TimeoutExpired:
                result["outcome"] = "timeout"
            finally:
                # Stop the whole group, including children left by a completed parent.
                _stop(process)
    except OSError as error:
        result.update(outcome="error", error=str(error))
    result["durationSeconds"] = time.monotonic() - started
    return result


def _source(root: Path, manifest: MutationManifest) -> tuple[Path, bytes, bytes]:
    relative = Path(manifest.path)
    path = (root / relative).resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
        raise ValueError(f"Unsafe mutation path: {manifest.path}")
    original = path.read_bytes()
    start, end = manifest.span.startByte, manifest.span.endByte
    expected = base64.b64decode(manifest.originalBytes, validate=True)
    if (hashlib.sha256(original).hexdigest() != manifest.sourceHash
            or not 0 <= start < end <= len(original) or original[start:end] != expected):
        raise ValueError(f"Stale mutation source: {manifest.path}")
    replacement = base64.b64decode(manifest.replacementBytes, validate=True)
    return path, original, original[:start] + replacement + original[end:]


@contextmanager
def _interrupt_on_termination() -> Iterator[None]:
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


class MutationRunner:
    """Execute explicit targets in the caller's workspace, without a baseline."""

    def __init__(self, root: Path, config: MutationConfig):
        self.root = root.resolve()
        self.config = config
        self.directories = _working_directories(self.root, config)

    def _execute(self, manifest: MutationManifest, logs: Path, ordinal: int) -> dict:
        result: dict = {"manifestId": manifest.id, "path": manifest.path, "ruleId": manifest.ruleId,
                        "outcome": "unmapped", "targets": []}
        targets = matching_targets(manifest.path, self.config)
        if not targets:
            return result
        try:
            path, original, modified = _source(self.root, manifest)
        except (OSError, ValueError) as error:
            return {**result, "outcome": "error", "error": str(error)}
        try:
            path.write_bytes(modified)
            for index, (name, target) in enumerate(targets.items()):
                execution = _run_command(target, self.directories[name], logs / f"{ordinal}-{index}.log")
                result["targets"].append({"name": name, **execution})
        except OSError as error:
            return {**result, "outcome": "error", "error": str(error)}
        finally:
            # Restoration failures must abort, not continue with corrupted source.
            path.write_bytes(original)
        outcomes = {execution["outcome"] for execution in result["targets"]}
        result["outcome"] = next(outcome for outcome in ("killed", "error", "timeout", "survived") if outcome in outcomes)
        return result

    def run(self, manifests: list[MutationManifest], output: Path) -> dict[str, int]:
        """Flush each JSONL result; refuse to overwrite existing results.

        SIGINT/SIGTERM restore source; SIGKILL and machine failure cannot.
        Commands are trusted and may modify other project files.
        """
        output = output.resolve()
        logs = output.with_name(output.name + ".logs")
        counts: dict[str, int] = {}
        with _interrupt_on_termination(), output.open("x", encoding="utf-8") as stream:
            logs.mkdir()
            for ordinal, manifest in enumerate(manifests):
                result = self._execute(manifest, logs, ordinal)
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                stream.flush()
                outcome = result["outcome"]
                counts[outcome] = counts.get(outcome, 0) + 1
        return counts
