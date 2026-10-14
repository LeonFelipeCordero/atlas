"""Markdown reports preserve evidence/provenance without conflating outcomes."""

from pathlib import Path

from atlas.domain.mutation import MutationDiagnostic, MutationTrial
from atlas.mutation.reporting import render_mutation_markdown
from atlas.services.mutation import build_report
from tests.mutation_support import ledger_session, trial_input


def test_report_preserves_all_trial_outcomes_and_unexplored_sites(tmp_path: Path) -> None:
    session = ledger_session(tmp_path)
    results = []
    for outcome in ("killed", "survived", "invalid", "timeout", "error", "skipped"):
        data = trial_input().model_dump()
        data["outcome"] = outcome
        data["mutant"]["exit_code"] = 0 if outcome == "survived" else 1
        results.append(MutationTrial.model_validate({
            "trial_id": outcome, "session_id": session.session_id, "site_id": "site-1",
            "recorded_at": "now", "result": data,
        }))
    report = build_report(session, results)
    assert report["outcome_counts"] == dict.fromkeys(("killed", "survived", "invalid", "timeout", "error", "skipped"), 1)
    markdown = render_mutation_markdown(report)
    assert "not independently verified" in markdown
    assert "no recorded trial): 0" in markdown
    for trial in results:
        assert f"{trial.result.outcome} (agent-reported)" in markdown
        assert trial.result.hypothesis in markdown
        assert trial.result.source_identity.original_file_hash in markdown
    assert "baseline.log" in markdown and "mutant.log" in markdown


def test_report_escapes_source_table_text_and_keeps_patch_indented(tmp_path: Path) -> None:
    session = ledger_session(tmp_path)
    source = session.sources[0].model_copy(update={"path": "a|b\nfile.py"})
    session = session.model_copy(update={
        "sources": [source],
        "limitations": [MutationDiagnostic(path="a|b\nfile.py", code="unsupported-condition", message="An explicit limitation")],
    })
    result = trial_input().model_copy(update={"patch": "```\n# not a heading\n```"})
    trial = MutationTrial(trial_id="trial", session_id=session.session_id, site_id="site-1", recorded_at="now", result=result)
    markdown = render_mutation_markdown(build_report(session, [trial]))
    assert r"a\|b file.py" in markdown
    assert "    ```\n    # not a heading\n    ```" in markdown
    assert "An explicit limitation" in markdown


def test_unexplored_report_keeps_scope_coordinates_and_context(tmp_path: Path) -> None:
    session = ledger_session(tmp_path)
    markdown = render_mutation_markdown(build_report(session, []))
    assert "folders: ." in markdown
    assert "Unexplored: no recorded trial" in markdown
    assert "byte columns" in markdown
    assert "def accept(amount, minimum):" in markdown
    assert "None reported; this is not a claim of complete mutation coverage" in markdown
