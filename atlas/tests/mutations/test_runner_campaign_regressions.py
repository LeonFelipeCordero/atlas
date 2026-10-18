"""Safety and timing gaps from the completed mutation campaign."""

import base64
import os
from unittest.mock import Mock

import pytest

from atlas.domain.models import SourceFile
from atlas.mutations import runner
from atlas.mutations.config import MutationConfig, MutationTarget
from atlas.mutations.manifests import generate_manifests
from atlas.parsing.mutation_candidates import extract_candidates


@pytest.fixture
def source_manifest(tmp_path):
    path = tmp_path / "source.py"
    path.write_bytes(b"x = 1 < 2\n")
    source = SourceFile(path=path.name, absolute_path=path, language="python", source=path.read_bytes())
    manifest = generate_manifests(tmp_path, extract_candidates(source).candidates,
                                  ["comparison.less-to-greater"])[0]
    return path, manifest


@pytest.mark.parametrize("path", ["src/wrong.py", "src/a/wrong.py", "wrong.py"])
def test_recursive_glob_requires_final_filename(path):
    config = MutationConfig(targets={"unit": MutationTarget(sources=["src/**/right.py"], command=["true"])})
    assert runner.matching_targets(path, config) == {}


@pytest.mark.parametrize("case", ["absolute", "parent", "symlink"])
def test_source_rejects_each_unsafe_path_independently(tmp_path, source_manifest, case):
    path, manifest = source_manifest
    if case == "absolute":
        unsafe = str(path)
    elif case == "parent":
        (tmp_path / "nested").mkdir()
        unsafe = "nested/../source.py"
    else:
        outside = tmp_path.parent / (tmp_path.name + "-outside.py")
        outside.write_bytes(path.read_bytes())
        (tmp_path / "link.py").symlink_to(outside)
        unsafe = "link.py"
    with pytest.raises(ValueError, match="Unsafe mutation path"):
        runner._source(tmp_path, manifest.model_copy(update={"path": unsafe}))
    assert path.read_bytes() == b"x = 1 < 2\n"


@pytest.mark.parametrize("change", [{"sourceHash": "0" * 64}, {"originalBytes": "Pw=="}])
def test_hash_and_expected_token_are_independent_guards(tmp_path, source_manifest, change):
    _, manifest = source_manifest
    with pytest.raises(ValueError, match="Stale mutation source"):
        runner._source(tmp_path, manifest.model_copy(update=change))


@pytest.mark.parametrize("case", [(0, 1, True), (9, 10, True), (0, 0, False), (-1, 1, False), (9, 11, False)])
def test_exact_span_boundaries(tmp_path, source_manifest, case):
    start, end, valid = case
    path, manifest = source_manifest
    original = path.read_bytes()
    span = manifest.span.model_copy(update={"startByte": start, "endByte": end})
    manifest = manifest.model_copy(update={"span": span, "originalBytes": base64.b64encode(original[start:end]).decode()})
    if valid:
        assert runner._source(tmp_path, manifest)[2] == original[:start] + b">" + original[end:]
    else:
        with pytest.raises(ValueError, match="Stale mutation source"):
            runner._source(tmp_path, manifest)


def test_command_duration_and_process_group_contract(tmp_path, monkeypatch):
    process = Mock()
    process.wait.return_value = 0
    popen = Mock(return_value=process)
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner, "_stop", Mock())
    monkeypatch.setattr(runner.time, "monotonic", Mock(side_effect=[100, 103.25]))
    target = MutationTarget(sources=["*.py"], command=["true"])
    result = runner._run_command(target, tmp_path, tmp_path / "command.log")
    assert result["durationSeconds"] == 3.25
    assert result["outcome"] == "survived"
    assert popen.call_args.kwargs["start_new_session"] is (os.name == "posix")


def test_total_duration_is_elapsed_time(tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(runner.time, "monotonic", Mock(side_effect=[100, 104.5]))
    assert runner.MutationRunner(tmp_path, MutationConfig(), messages.append).run([], tmp_path / "results") == {}
    assert messages[-1] == "Completed 0 mutations in 4.50s: {}"
