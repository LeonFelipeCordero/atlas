"""One run owns its results, action filter, and per-project action budget."""
from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass, field


@dataclass
class Run:
    args: argparse.Namespace
    records: list[dict] = field(default_factory=list)
    coverage: list[dict] = field(default_factory=list)
    case_count: int = 0

    def selected(self, case) -> bool:
        return not self.args.actions or any(fnmatch.fnmatchcase(case.name, pattern) for pattern in self.args.actions)

    def exhausted(self) -> bool:
        return self.args.max_cases is not None and self.case_count >= self.args.max_cases

    def save(self, record: dict) -> None:
        with (self.args.output / "measurements.jsonl").open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.records.append(self.compact(record))

    def compact(self, record: dict) -> dict:
        result = dict(record)
        if record["passed"] and "python" in record:
            result["python"] = {"elapsed_ns": record["python"]["elapsed_ns"]}
            result["rust"] = {"elapsed_ns": record["rust"]["elapsed_ns"]}
        return result
