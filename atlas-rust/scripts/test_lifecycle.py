"""Regression guards for timestamp masking and real historical fixtures."""
import copy
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from common import Process, require
from database import contents
from lifecycle import REVISIONS, historical, verify_replacement_baseline
from pairing import REFERENCE
from timestamps import WriteTimestamps


class TimestampTests(unittest.TestCase):
    def setUp(self):
        self.before: dict = {"data": {"repositories": [{"id": "r", "created_at": 1000}],
                                "repository_graphs": [{"repository_id": "r", "imported_at": 2000,
                                                       "indexed_at": "1970-01-01T00:00:02+00:00", "graph_revision": "old"}]}}
        self.after: dict = copy.deepcopy(self.before)
        self.after["data"]["repository_graphs"][0].update(imported_at=3000, indexed_at="1970-01-01T00:00:03+00:00", graph_revision="new")
        self.result = {"exit_code": 0, "started_ms": 2900, "finished_ms": 3100, "stdout": ""}

    def check(self, migration=False):
        return WriteTimestamps(self.result, migration, "/timestamps").compare(self.before, self.after)

    def test_valid_replacement_and_immutable_created_at(self):
        self.assertEqual(self.check(), [])
        self.after["data"]["repositories"][0]["created_at"] = 3000
        self.assertTrue(self.check())

    def test_invalid_stale_future_null_and_wrong_type_import_times(self):
        invalid = [("imported_at", value) for value in (0, 2000, 9999, None, "bad", True)]
        invalid += [("indexed_at", value) for value in ("bad", "1970-01-01T00:00:03", None, "1970-01-01T00:00:02Z")]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                self.setUp()
                self.after["data"]["repository_graphs"][0][field] = value
                self.assertTrue(self.check())

    def test_migrations_preserve_timestamps_exactly(self):
        self.assertTrue(self.check(migration=True))
        self.after = copy.deepcopy(self.before)
        self.assertEqual(self.check(migration=True), [])

    def test_failed_write_cannot_change_import_time_without_revision(self):
        self.result["exit_code"] = 1
        self.after["data"]["repository_graphs"][0]["graph_revision"] = "old"
        self.assertTrue(self.check())

    def test_first_write_and_output_timestamp_validation(self):
        self.before = {"exists": False}
        self.after["data"]["repositories"][0]["created_at"] = 3000
        self.assertEqual(self.check(), [])
        self.result["stdout"] = '{"importedAt":0}'
        self.assertTrue(self.check())


class HistoricalTests(unittest.TestCase):
    def test_actual_revision_schemas_and_population(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / "source"
            root.mkdir()
            (root / "sample.py").write_text("def old():\n    return 1\n\ndef caller():\n    return old()\n")
            baseline = folder / "baseline.sqlite"
            for args in (["seed", str(baseline), str(root)], ["cli", "index"]):
                require(Process([sys.executable, str(REFERENCE), *args], root, baseline, 30).run(), "fixture")
            with self.assertRaisesRegex(ValueError, "excluded the replacement fixture"):
                verify_replacement_baseline(SimpleNamespace(baseline=baseline, ready=lambda: True))
            for revision in REVISIONS:
                target = folder / f"{revision}.sqlite"
                historical(target, revision, baseline)
                self.assert_revision(target, revision)

    def assert_revision(self, target, revision):
        snapshot = contents(target)
        self.assertEqual(snapshot["data"]["alembic_version"], [{"version_num": revision}])
        self.assertEqual(len(snapshot["data"]["repositories"]), 2)
        self.assertEqual(len(snapshot["data"]["repository_graphs"]), 2)
        self.assertEqual(snapshot["foreign_key_check"], [])
        if revision != REVISIONS[0]:
            self.assertTrue(snapshot["data"]["graph_nodes"])
        if revision in REVISIONS[2:]:
            self.assertTrue(snapshot["data"]["graph_edges"])
        with sqlite3.connect(target) as database:
            columns = [row[1] for row in database.execute("PRAGMA table_info(repository_graphs)")]
        self.assertEqual("artifact" in columns, revision != REVISIONS[-1])


if __name__ == "__main__":
    unittest.main()
