"""Compare both runtimes on identical isolated inputs, including every SQLite row."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cases import Case
from common import Process, differences, normalize, result_value
from database import backup, contents, revision, uuid_fixture
from timestamps import WriteTimestamps, output_diffs

if TYPE_CHECKING:
    from project import Project

REFERENCE = Path(__file__).with_name("reference.py")


@dataclass
class Pair:
    project: Project
    case: Case
    folder: Path

    def databases(self) -> tuple[Path, Path]:
        paths = self.folder / "python.sqlite", self.folder / "rust.sqlite"
        if self.case.name != "migrate.fresh":
            backup(self.project.baseline, paths[0])
            backup(self.project.baseline, paths[1])
        return paths

    def native(self, database: Path) -> dict:
        args = self.project.run.args
        command = [str(args.rust_migrate)] if self.case.migration else [str(args.rust_bin), *self.case.args]
        return Process(command, self.project.root, database, args.timeout).run()

    def fixture(self, database: Path) -> tuple[dict, list[dict]]:
        try:
            identity = uuid_fixture(database)
            if identity is None or identity == revision(self.project.baseline):
                raise ValueError("write must create a fresh UUID4 revision")
            fixture = {"ATLAS_PARITY_UUID": identity}
            if self.case.name == "index.first":
                from uuid import UUID
                rows = contents(database)["data"]["repositories"]
                if len(rows) != 1 or str(UUID(rows[0]["id"], version=4)) != rows[0]["id"]:
                    raise ValueError("first index must create one canonical UUID4 repository")
                fixture["ATLAS_PARITY_REPOSITORY_UUID"] = rows[0]["id"]
            return fixture, []
        except ValueError as error:
            return {}, [{"path": "/database/graph_revision", "error": str(error)}]

    def entropy(self, native: tuple[Path, dict]) -> tuple[dict, list[dict]]:
        database, result = native
        if self.case.writes and not self.case.migration and self.valid_reference(result):
            return self.fixture(database)
        return {}, []

    def reference(self, database: Path, fixture: dict) -> dict:
        mode = "migrate" if self.case.migration else "cli"
        command = [sys.executable, str(REFERENCE), mode, *self.case.args]
        return Process(command, self.project.root, database, self.project.run.args.timeout, fixture).run()

    def database_diffs(self, paths: tuple[Path, Path]) -> list[dict]:
        expected, actual = map(contents, paths)
        root = self.project.root
        diffs = []
        if not self.case.writes:
            original = contents(self.project.baseline)
            diffs.extend(differences(original, actual, "/read_only/rust"))
            diffs.extend(differences(original, expected, "/read_only/python"))
        # SeaORM owns Rust migration tracking; all shared schema and data must still match.
        for section in (expected.get("schema", {}), expected.get("data", {}),
                        actual.get("schema", {}), actual.get("data", {})):
            section.pop("seaql_migrations", None)
        diffs.extend(differences(normalize(expected, root), normalize(actual, root), "/database"))
        return diffs

    def outcome_diffs(self, python: dict, rust: dict) -> list[dict]:
        root = self.project.root
        diffs = differences(result_value(python, root), result_value(rust, root), "/result")
        if python["timeout"] or rust["timeout"]:
            diffs.append({"path": "/result/timeout", "error": "timeouts never pass parity"})
        if self.case.valid and not self.valid_reference(python):
            diffs.append({"path": "/reference", "error": "unexpected reference failure"})
        return diffs

    def valid_reference(self, result: dict) -> bool:
        if result["exit_code"] == 0:
            return True
        return self.case.args[:1] == ("check",) and result["exit_code"] == 1 and not result["stderr"]

    def execute(self) -> dict:
        from lifecycle import prepare
        prepare(self)
        py_db, rust_db = self.databases()
        before = contents(py_db)
        rust = self.native(rust_db)
        fixture, diffs = self.entropy((rust_db, rust))
        python = self.reference(py_db, fixture)
        diffs.extend(self.outcome_diffs(python, rust))
        diffs.extend(self.database_diffs((py_db, rust_db)))
        for label, database, result in (("python", py_db, python), ("rust", rust_db, rust)):
            after = contents(database)
            path = f"/timestamps/{label}"
            if self.case.writes:
                diffs.extend(WriteTimestamps(result, self.case.migration, path).compare(before, after))
            else:
                diffs.extend(output_diffs(after.get("data", {}), result, path + "/output"))
        return {"case": self.case.name, "args": self.case.args, "python": python, "rust": rust,
                "uuid_fixture": fixture.get("ATLAS_PARITY_UUID"), "diffs": diffs, "passed": not diffs}
