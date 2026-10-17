"""Autonomous execution uses real subprocesses, exact bytes, and no baseline."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from atlas.domain.models import SourceFile
from atlas.mutations.config import MutationConfig, MutationTarget
from atlas.mutations.manifests import generate_manifests
from atlas.mutations.runner import MutationRunner, matching_targets
from atlas.parsing.mutation_candidates import extract_candidates


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "source.py"
    original = '# café\r\nvalue = 1 < 2\r\n'.encode()
    path.write_bytes(original)
    source = SourceFile(path="source.py", absolute_path=path, language="python", source=original)
    candidates = extract_candidates(source).candidates
    manifests = generate_manifests(tmp_path, candidates, ["comparison.less-to-less-equal", "comparison.less-to-greater"])
    return tmp_path, path, original, manifests


def config(script, **overrides):
    return MutationConfig(targets={"unit": MutationTarget(
        sources=["source.py"], command=[sys.executable, "-c", script], **overrides)})


def results(root):
    return [json.loads(line) for line in (root / "results.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("exit_code,outcome", [(0, "survived"), (1, "killed"), (5, "killed")])
def test_each_mutation_is_independent_and_captures_logs(project, exit_code, outcome):
    root, path, original, manifests = project
    script = f"from pathlib import Path; import sys; print(Path('source.py').read_text()); sys.exit({exit_code})"
    counts = MutationRunner(root, config(script)).run(manifests, root / "results.jsonl")
    assert counts == {outcome: 2}
    assert path.read_bytes() == original
    for manifest, result in zip(manifests, results(root)):
        assert result["manifestId"] == manifest.id
        execution = result["targets"][0]
        assert execution["exitCode"] == exit_code
        assert manifest.replacement in Path(execution["log"]).read_text()
        assert execution["durationSeconds"] >= 0
    assert len(results(root)) == 2  # No unchanged baseline execution.


def test_unmapped_source_is_not_modified(project):
    root, path, original, manifests = project
    counts = MutationRunner(root, MutationConfig()).run(manifests, root / "results.jsonl")
    assert counts == {"unmapped": 2}
    assert path.read_bytes() == original
    assert all(not item["targets"] for item in results(root))


def test_all_matching_targets_run_and_any_kill_wins(project):
    root, path, original, manifests = project
    settings = config("raise SystemExit(1)")
    settings.targets["other"] = MutationTarget(sources=["*.py"], command=[sys.executable, "-c", "print('other')"])
    MutationRunner(root, settings).run(manifests[:1], root / "results.jsonl")
    result = results(root)[0]
    assert result["outcome"] == "killed"
    assert [item["outcome"] for item in result["targets"]] == ["killed", "survived"]
    assert path.read_bytes() == original


def test_timeout_restores_source(project):
    root, path, original, manifests = project
    counts = MutationRunner(root, config("import time; time.sleep(60)", timeoutSeconds=1)).run(manifests[:1], root / "results.jsonl")
    assert counts == {"timeout": 1}
    assert path.read_bytes() == original


def test_missing_executable_is_error(project):
    root, path, original, manifests = project
    settings = config("pass")
    settings.targets["unit"].command = [str(root / "missing-command")]
    assert MutationRunner(root, settings).run(manifests[:1], root / "results.jsonl") == {"error": 1}
    assert "error" in results(root)[0]["targets"][0]
    assert path.read_bytes() == original


def test_stale_source_is_not_overwritten(project):
    root, path, _, manifests = project
    path.write_bytes(b"user edit")
    assert MutationRunner(root, config("pass")).run(manifests, root / "results.jsonl") == {"error": 2}
    assert path.read_bytes() == b"user edit"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, RuntimeError("interrupted")])
def test_exception_restores_source_and_keeps_completed_results(project, exception):
    root, path, original, manifests = project
    from atlas.mutations import runner

    real_command = runner._run_command
    calls = 0

    def interrupt(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise exception
        return real_command(*args)

    with patch.object(runner, "_run_command", side_effect=interrupt), pytest.raises(type(exception) if isinstance(exception, Exception) else exception):
        MutationRunner(root, config("pass")).run(manifests, root / "results.jsonl")
    assert path.read_bytes() == original
    assert len(results(root)) == 1


def test_existing_results_are_never_overwritten(project):
    root, path, original, manifests = project
    output = root / "results.jsonl"
    output.write_text("existing")
    with pytest.raises(FileExistsError):
        MutationRunner(root, config("pass")).run(manifests, output)
    assert output.read_text() == "existing"
    assert path.read_bytes() == original


@pytest.mark.parametrize("cwd", ["missing", ".."])
def test_invalid_working_directory_fails_before_mutation(project, cwd):
    root, path, original, manifests = project
    with pytest.raises(ValueError, match="working directory"):
        MutationRunner(root, config("pass", cwd=cwd)).run(manifests, root / "results.jsonl")
    assert not (root / "results.jsonl").exists()
    assert path.read_bytes() == original


@pytest.mark.parametrize("change", [
    {"sources": []}, {"sources": [""]}, {"sources": ["../escape/**"]},
    {"sources": ["/absolute/**"]}, {"sources": ["a\\b"]}, {"command": []},
    {"command": [""]}, {"timeoutSeconds": 0}, {"timeoutSeconds": True},
])
def test_target_validation(change):
    with pytest.raises(ValidationError):
        MutationTarget.model_validate({"sources": ["src/**"], "command": ["pytest"], **change})


@pytest.mark.parametrize("pattern,path,expected", [
    ("src/module/**", "src/module/nested/file.py", True),
    ("src/module/**", "src/module_other/file.py", False),
    ("src/*.py", "src/nested/file.py", False),
    ("src/*.py", "src/file.py", True),
    ("src/**/file.py", "src/file.py", True),
    ("src/**/file.py", "src/a/b/file.py", True),
    ("src/test_?.py", "src/test_a.py", True),
    ("src/[ab].py", "src/c.py", False),
])
def test_source_globs(pattern, path, expected):
    settings = config("pass")
    settings.targets["unit"].sources = [pattern]
    assert bool(matching_targets(path, settings)) == expected


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")
def test_sigterm_restores_source(project):
    root, path, original, manifests = project
    previous = signal.getsignal(signal.SIGTERM)
    script = "import os, signal; os.kill(os.getppid(), signal.SIGTERM)"
    with pytest.raises(KeyboardInterrupt):
        MutationRunner(root, config(script)).run(manifests[:1], root / "results.jsonl")
    assert path.read_bytes() == original
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")
def test_timeout_kills_children(project):
    root, path, original, manifests = project
    child = "import time; from pathlib import Path; time.sleep(2); Path('leaked').touch()"
    script = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
    MutationRunner(root, config(script, timeoutSeconds=1)).run(manifests[:1], root / "results.jsonl")
    subprocess.run([sys.executable, "-c", "import time; time.sleep(2)"], check=True)
    assert not (root / "leaked").exists()
    assert path.read_bytes() == original


def test_restoration_failure_aborts_before_the_next_mutation(project):
    from atlas.mutations import runner

    root, path, original, manifests = project
    write_bytes = Path.write_bytes
    restorations = 0

    def fail_second_restore(destination, data):
        nonlocal restorations
        if destination == path and data == original:
            restorations += 1
            if restorations == 2:
                raise OSError("restore failed")
        return write_bytes(destination, data)

    with (patch.object(Path, "write_bytes", autospec=True, side_effect=fail_second_restore),
          patch.object(runner, "_run_command", wraps=runner._run_command) as command):
        with pytest.raises(OSError, match="restore failed"):
            MutationRunner(root, config("pass")).run(manifests * 2, root / "results.jsonl")
    assert command.call_count == 2
    assert len(results(root)) == 1
    assert path.read_bytes() != original
    path.write_bytes(original)


def test_python_commands_do_not_reuse_baseline_bytecode(project):
    import py_compile
    from atlas.mutations import runner

    root, path, original, manifests = project
    py_compile.compile(str(path), doraise=True)
    timestamp = path.stat().st_mtime
    manifest = next(item for item in manifests if item.replacement == ">")
    real_command = runner._run_command

    def same_timestamp(*args):
        os.utime(path, (timestamp, timestamp))
        return real_command(*args)

    with patch.object(runner, "_run_command", side_effect=same_timestamp):
        counts = MutationRunner(root, config("import source; assert source.value is False")).run(
            [manifest], root / "results.jsonl")
    assert counts == {"survived": 1}
    assert path.read_bytes() == original
