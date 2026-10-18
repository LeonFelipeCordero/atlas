"""Keep clap presentation exceptions separate from strict data parity."""
from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from cases import Case
from interoperability import native_case
from pairing import Pair
from project import Project
from session import Run


def process(code: int, stdout: str = "", stderr: str = "") -> dict:
    return {"exit_code": code, "stdout": stdout, "stderr": stderr, "timeout": False}


class PresentationTests(unittest.TestCase):
    def pair(self, case: Case) -> Pair:
        root = Path("/tmp")
        return Pair(Project(Run(argparse.Namespace()), root, root), case, root)

    def test_help_can_differ_but_must_be_help(self):
        pair = self.pair(Case("help.atlas", ("--help",), presentation=True))
        python = process(0, "Click help")
        rust = process(0, "Usage: atlas <COMMAND>\n--help")
        self.assertEqual(pair.outcome_diffs(python, rust), [])
        for invalid in [process(0), process(0, "Usage: atlas"), process(1, stderr="Usage: atlas"),
                        process(0, rust["stdout"], "unexpected")]:
            self.assertTrue(pair.outcome_diffs(python, invalid))

    def test_errors_keep_exit_status_and_channel_contracts(self):
        pair = self.pair(Case("invalid", (), valid=False, presentation=True))
        python = process(2, stderr="Click diagnostic")
        self.assertEqual(pair.outcome_diffs(python, process(2, stderr="error: invalid\nTry --help")), [])
        self.assertTrue(pair.outcome_diffs(python, process(2, stderr="")))
        self.assertTrue(pair.outcome_diffs(python, process(1, stderr="Usage: atlas")))
        self.assertTrue(pair.outcome_diffs(python, process(2, "unexpected", "Usage: atlas")))

    def test_unsupported_group_terminators_have_explicit_native_status(self):
        pair = self.pair(Case("terminator", ("--", "projects"), presentation=True, native_exit_code=2))
        self.assertEqual(pair.outcome_diffs(process(0, "[]"), process(2, stderr="error: invalid\nTry --help")), [])
        self.assertTrue(pair.outcome_diffs(process(0, "[]"), process(0, "Usage: atlas --help")))

    def test_data_and_runtime_errors_still_compare_exactly(self):
        pair = self.pair(Case("projects", ("projects",)))
        self.assertTrue(pair.outcome_diffs(process(0, "[]"), process(0, "[1]")))
        pair = self.pair(Case("runtime-error", (), valid=False))
        self.assertTrue(pair.outcome_diffs(process(1, stderr="original"), process(1, stderr="changed")))

    def test_native_database_cases_keep_presentation_contracts(self):
        case = Case("graph.group.terminator", ("graph", "--", "overview"), presentation=True, native_exit_code=2)
        native = native_case(case, ("old", "new"))
        self.assertTrue(native.presentation)
        self.assertEqual(native.native_exit_code, 2)
        self.assertEqual(native.args, case.args)
        case = Case("graph.revision.valid", ("graph", "--revision", "old", "overview"))
        self.assertEqual(native_case(case, ("old", "new")).args, ("graph", "--revision", "new", "overview"))

    def test_timeouts_never_pass_presentation_checks(self):
        pair = self.pair(Case("help.atlas", ("--help",), presentation=True))
        result = process(0, "Usage: atlas --help")
        result["timeout"] = True
        self.assertTrue(pair.outcome_diffs(result, result))


if __name__ == "__main__":
    unittest.main()
