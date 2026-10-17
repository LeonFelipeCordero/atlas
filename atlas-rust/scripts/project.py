"""One project owns only temporary databases. All source roots remain read-only."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cases import Case, analysis_cases, navigation_cases, usage_cases
from common import SAMPLES, Process, require
from database import keys, languages, revision
from pairing import REFERENCE, Pair
from session import Run


@dataclass
class Project:
    run: Run
    root: Path
    folder: Path
    baseline: Path = field(init=False)

    def __post_init__(self) -> None:
        self.baseline = self.folder / "baseline.sqlite"

    def oracle(self, arguments: list[str]) -> dict:
        return Process([sys.executable, str(REFERENCE), *arguments], self.root, self.baseline, self.run.args.timeout).run()

    def prepare(self) -> None:
        require(self.oracle(["seed", str(self.baseline), str(self.root)]), "Python seed")
        result = self.oracle(["cli", "index", "-f", str(self.root)])
        if result["exit_code"] != 0 or result["timeout"]:
            self.run.save({"project": str(self.root), "case": "setup.reference.index", "phase": "setup", "passed": False,
                           "python": result, "error": "Reference indexing failed; graph-dependent cases are blocked"})

    def ready(self) -> bool:
        return revision(self.baseline) is not None

    def cases(self) -> list[Case]:
        node_keys = keys(self.baseline) if self.ready() else ("repository", "<unavailable-file>", "<unavailable-from>", "<unavailable-to>")
        cases = analysis_cases(self.root) + navigation_cases(self.root, node_keys, revision(self.baseline) or "") + usage_cases()
        return list(filter(self.run.selected, cases))

    def coverage(self, cases: list[Case]) -> None:
        inventory = json.loads(self.run.args.inventory.read_text()) if self.run.args.inventory else []
        self.run.coverage.append({"root": str(self.root), "reference_graph_ready": self.ready(), "languages": languages(self.baseline),
                                  "source_inventory": next((item for item in inventory if item.get("project") == str(self.root)), None),
                                  "actions": [case.name for case in cases]})

    def blocked(self, case: Case, reason: str) -> None:
        if self.run.exhausted():
            return
        self.run.case_count += 1
        self.run.save({"project": str(self.root), "case": case.name, "phase": "blocked", "passed": False, "error": reason})
        print(f"BLOCKED {self.root.name} {case.name}: {reason}", flush=True)

    def run_case(self, case: Case) -> None:
        if self.run.exhausted():
            return
        self.run.case_count += 1
        for iteration in range(self.run.args.warmups + self.run.args.repetitions):
            self.iteration(case, iteration)

    def iteration(self, case: Case, iteration: int) -> None:
        with tempfile.TemporaryDirectory(prefix="iteration-", dir=self.folder) as temporary:
            try:
                result = Pair(self, case, Path(temporary)).execute()
            except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
                result = {"case": case.name, "passed": False, "error": str(error)}
        phase = "warmup" if iteration < self.run.args.warmups else "measured"
        result.update(project=str(self.root), phase=phase, iteration=iteration)
        self.run.save(result)
        print(f"{'PASS' if result['passed'] else 'FAIL'} {self.root.name} {case.name} [{iteration + 1}]", flush=True)

    def dispatch(self, case: Case) -> None:
        needs_graph = case.name.startswith("graph.") or case.name == "mutations.saved"
        if needs_graph and not self.ready():
            self.blocked(case, "reference index failed or timed out")
        else:
            self.run_case(case)

    def canonical(self, prefix: str = "") -> None:
        if self.root.parent != SAMPLES:
            return
        from navigation import labels, replay
        if self.ready():
            replay(self, prefix)
        else:
            for label in labels(self.root):
                self.block_canonical(prefix + "navigation." + label)

    def block_canonical(self, name: str) -> None:
        case = Case(name, ())
        if self.run.selected(case):
            self.blocked(case, "reference index failed or timed out")

    def execute(self) -> None:
        self.prepare()
        cases = self.cases()
        self.coverage(cases)
        for case in cases:
            self.dispatch(case)
        self.canonical()
        self.interoperability(cases)
        self.variants()
        if not self.run.case_count:
            raise ValueError("No actions matched; use --list-actions")

    def interoperability(self, cases: list[Case]) -> None:
        from interoperability import compare
        compare(self, cases)

    def variants(self) -> None:
        if self.run.args.variants and self.root.parent == SAMPLES:
            from variants import run_variants
            run_variants(self)
