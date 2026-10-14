"""Markdown reports preserve evidence/provenance without conflating outcomes."""

from pathlib import Path

from atlas.domain.mutation import MutationDiagnostic, MutationTrial
from atlas.mutation.reporting import render_mutation_markdown
from atlas.services.mutation import build_report
from tests.mutation_support import ledger_session, trial_input


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

