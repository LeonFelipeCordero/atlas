"""Harness self-tests, including a real Python-oracle subprocess round trip."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cases import Case, analysis_cases, navigation_cases, usage_cases
from common import Process, differences, normalize, output_value
from database import backup, connect, contents, uuid_fixture
from pairing import Pair
from project import Project
from session import Run
from variants import definitions


class ComparisonTests(unittest.TestCase):
    def test_normalization_changes_only_roots_and_timestamps(self):
        value = {"root": "/checkout/python", "indexedAt": "today", "graphRevision": "revision", "repositoryId": "repo",
                 "nodes": [{"stableKey": "z"}, {"stableKey": "a"}], "sourceHash": "hash",
                 "evidence": "render()", "absolutePath": "/checkout/python/file.py", "createdAt": None}
        before = json.loads(json.dumps(value))
        actual = normalize(value, Path("/checkout/python"))
        self.assertEqual(actual, {**value, "root": "/samples/coffee/python", "indexedAt": "<timestamp:str>",
                                  "absolutePath": "/samples/coffee/python/file.py"})
        self.assertEqual(value, before)
        self.assertEqual(normalize("/checkout/pythonic", Path("/checkout/python")), "/checkout/pythonic")
        self.assertEqual(normalize({"evidence": "/checkout/python", "lines": ["/checkout/python"]}, Path("/checkout/python")),
                         {"evidence": "/checkout/python", "lines": ["/checkout/python"]})
        self.assertTrue(differences(normalize({"indexedAt": 1}, Path("/root")), normalize({"indexedAt": "1"}, Path("/root"))))

    def test_array_order_missing_null_numbers_and_types_fail(self):
        for left, right in [(["z", "a"], ["a", "z"]), ({"x": None}, {}), (1, 1.0), (True, 1), ([1], [1, 2])]:
            self.assertTrue(differences(left, right), (left, right))
        self.assertEqual(differences({"b": 2, "a": 1}, {"a": 1, "b": 2}), [])
        self.assertEqual(differences({"a/b~": 1}, {"a/b~": 2})[0]["path"], "/a~1b~0")

    def test_source_text_preserves_body_and_normalizes_header_only(self):
        text = '{"indexedAt":"today","graphRevision":"revision"}\n\n### source\n1: print(1)\n'
        actual = output_value(text, Path("/checkout/python"))
        self.assertIn('"graphRevision": "revision"', actual)
        self.assertIn('"indexedAt": "<timestamp:str>"', actual)
        self.assertTrue(actual.endswith("\n\n### source\n1: print(1)\n"))
        self.assertTrue(differences(text, text.rstrip()))

    def test_action_matrix_covers_commands_and_flags(self):
        cases = analysis_cases(Path("/sample")) + navigation_cases(Path("/sample"), ("r", "f", "a", "b"), "revision") + usage_cases()
        self.assertEqual(len(cases), len({case.name for case in cases}))
        flags = {arg for case in cases for arg in case.args if arg.startswith("-")}
        self.assertTrue({"-f", "--f", "--folder", "--save", "--saved", "--rules", "--format", "--project", "--revision",
                         "--limit", "--offset", "--direction", "--relations", "--depth", "--max-depth", "--max-nodes",
                         "--max-edges", "--max-lines", "--start-line", "--help"} <= flags)
        self.assertTrue(any(case.name == "graph.source.True.text.True" for case in cases))
        self.assertTrue(Run(argparse.Namespace(actions=["graph.source.*"])).selected(Case("graph.source.one", ())))
        self.assertEqual(len([item for item in definitions() if item[0].startswith("invalid")]), 8)

    def test_option_regressions_stay_in_matrix(self):
        root = Path("/sample")
        cases = analysis_cases(root) + navigation_cases(root, ("r", "f", "a", "b"), "revision") + usage_cases()
        expected = {"report.folder.attached", "mutations.folder.attached", "projects.group.terminator",
                    "report.help.folder.value", "report.help.format.value", "mutations.help.folder.value",
                    "mutations.help.literal", "graph.group.terminator", "graph.group.root.terminator",
                    "graph.find.literal.help", "help.group.terminator", "invalid.group.help.trailing.flag",
                    "invalid.graph.group.help.trailing.value", "help.graph.group.selector",
                    "invalid.group.option.command", "invalid.graph.group.option.command",
                    "invalid.command.suggest.root", "invalid.command.suggest.graph", "invalid.command.suggest.unicode"}
        self.assertTrue(expected <= {case.name for case in cases})


class DatabaseTests(unittest.TestCase):
    def test_read_only_connections_close_between_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.sqlite"
            sqlite3.connect(path).close()
            with connect(path) as connection:
                self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_backup_and_complete_schema_data_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, clone = root / "original.sqlite", root / "clone.sqlite"
            with sqlite3.connect(original) as database:
                database.executescript("CREATE TABLE item(id INTEGER PRIMARY KEY, payload TEXT); CREATE UNIQUE INDEX names ON item(payload);")
                database.execute("INSERT INTO item VALUES(?, ?)", (1, '{"nodes":["z","a"]}'))
            backup(original, clone)
            self.assertEqual(contents(original), contents(clone))
            with sqlite3.connect(clone) as database:
                database.execute("UPDATE item SET payload=?", ('{"nodes":["a","z"]}',))
            self.assertTrue(differences(contents(original), contents(clone)))
            with sqlite3.connect(clone) as database:
                database.execute("DROP INDEX names")
            self.assertTrue(differences(contents(original)["schema"], contents(clone)["schema"]))

    def test_read_only_timestamp_changes_are_not_masked(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            baseline = folder / "baseline.sqlite"
            with sqlite3.connect(baseline) as database:
                database.executescript("CREATE TABLE item(created_at INTEGER); INSERT INTO item VALUES(1);")
            project = Project(Run(argparse.Namespace()), folder, folder)
            project.baseline = baseline
            pair = Pair(project, Case("projects", ("projects",)), folder)
            python, rust = pair.databases()
            with sqlite3.connect(rust) as database:
                database.execute("UPDATE item SET created_at=2")
            diffs = pair.database_diffs((python, rust))
            self.assertTrue(any(diff["path"].startswith("/read_only/rust") for diff in diffs))

    def test_invalid_revision_is_not_masked(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "database.sqlite"
            with sqlite3.connect(path) as database:
                database.executescript("CREATE TABLE repository_graphs(graph_revision TEXT); INSERT INTO repository_graphs VALUES('bad');")
            with self.assertRaises(ValueError):
                uuid_fixture(path)


class TimeoutTests(unittest.TestCase):
    def test_process_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = Process([sys.executable, "-c", "import time; time.sleep(2)"], folder, folder / "db", 0.02).run()
            self.assertTrue(result["timeout"])
            self.assertIsNone(result["exit_code"])
            self.assertLess(result["elapsed_ns"], 1_000_000_000)

    def test_equal_timeouts_fail_and_next_action_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            baseline = folder / "baseline.sqlite"
            with sqlite3.connect(baseline) as database:
                database.execute("CREATE TABLE item(id INTEGER)")
            args = argparse.Namespace(timeout=1, rust_bin=Path("native"), max_cases=None, output=folder,
                                      warmups=0, repetitions=1)
            project = Project(Run(args), folder, folder)
            project.baseline = baseline
            timeout = {"exit_code": None, "stdout": "", "stderr": "", "timeout": True, "elapsed_ns": 1}
            with patch.object(Process, "run", return_value=timeout):
                result = Pair(project, Case("projects", ("projects",)), folder).execute()
            self.assertFalse(result["passed"])
            self.assertTrue(any(diff["path"] == "/result/timeout" for diff in result["diffs"]))
            successful = {"case": "next", "passed": True, "python": {"elapsed_ns": 1}, "rust": {"elapsed_ns": 1}}
            with patch.object(Pair, "execute", side_effect=[result, successful]):
                project.run_case(Case("timeout", ()))
                project.run_case(Case("next", ()))
            self.assertEqual([row["passed"] for row in project.run.records], [False, True])


class OracleRoundTripTests(unittest.TestCase):
    def test_controlled_entropy_allows_full_row_parity_and_detects_output_corruption(self):
        # This executable tests the harness, not the native port. CI still runs real Rust.
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / "sample"
            root.mkdir()
            (root / "coffee.py").write_text("def brew():\n    return 1 + 2\n")
            executable = folder / "oracle-native"
            reference = Path(__file__).with_name("reference.py")
            executable.write_text(f"#!{sys.executable}\nimport runpy,sys\nsys.argv=[{str(reference)!r},'cli',*sys.argv[1:]]\nrunpy.run_path({str(reference)!r},run_name='__main__')\n")
            executable.chmod(0o700)
            args = argparse.Namespace(timeout=30, rust_bin=executable, rust_migrate=executable, output=folder,
                                      max_cases=None, warmups=0, repetitions=1, actions=[], inventory=None, variants=False)
            project = Project(Run(args), root, folder)
            project.prepare()
            for case in [Case("index", ("index",), True), Case("report", ("report", "--format", "json"))]:
                work = folder / case.name
                work.mkdir()
                result = Pair(project, case, work).execute()
                self.assertEqual(result["diffs"], [], result)
            self.invalid_config_preserves_revision(project)
            executable.write_text(f"#!{sys.executable}\nprint('{{\"wrong\":true}}')\n")
            work = folder / "corrupt"
            work.mkdir()
            result = Pair(project, Case("projects", ("projects",)), work).execute()
            self.assertFalse(result["passed"])
            self.assertTrue(any(diff["path"].startswith("/result/stdout") for diff in result["diffs"]))
            self.assertFalse((root / "__pycache__").exists())
            self.assertEqual(os.stat(root / "coffee.py").st_size, 29)
            self.baseline_timeout_continues(project)

    def invalid_config_preserves_revision(self, project):
        config = project.root / "atlas.json"
        config.write_text('{"unknown":1}')
        work = project.folder / "invalid-config"
        work.mkdir()
        case = Case("invalid-config", ("check", "--save", "--format", "json"), True, valid=False)
        result = Pair(project, case, work).execute()
        config.unlink()
        self.assertEqual(result["diffs"], [], result)
        self.assertIsNone(result["uuid_fixture"])

    def baseline_timeout_continues(self, project):
        # A failed index must not prevent reports, projects, help, or later roots.
        args = project.run.args
        args.actions, args.max_cases = ["projects", "report.json.fresh"], 2
        project.run.records.clear()
        original = project.oracle
        timeout = {"exit_code": None, "stdout": "", "stderr": "", "timeout": True, "elapsed_ns": 1}
        def oracle(arguments):
            return timeout if arguments[:2] == ["cli", "index"] else original(arguments)
        with patch.object(project, "oracle", side_effect=oracle):
            # prepare() needs a fresh registration database.
            project.baseline.unlink()
            project.execute()
        self.assertEqual([record["case"] for record in project.run.records],
                         ["setup.reference.index", "projects", "report.json.fresh"])
        self.assertFalse(project.run.records[0]["passed"])


if __name__ == "__main__":
    unittest.main()
