"""Live Python/Rust mutation CLI parity, including stderr and command artifacts.

Run with: uv run --project atlas python -m unittest discover -s atlas-rust/scripts -p test_mutation_run.py
Build atlas-rust/target/debug/atlas first. Only measured durations are masked.
"""
import json
import os
import pty
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUST = Path(os.environ.get("ATLAS_RUST_BINARY", str(ROOT / "atlas-rust/target/debug/atlas")))
REFERENCE = ROOT / "atlas-rust/scripts/reference.py"


def limit_file_size():
    resource.setrlimit(resource.RLIMIT_FSIZE, (100, 100))
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)


def duration_mask(text):
    return re.sub(r"\d+\.\d{2}s", "<duration>s", text)


def record_mask(text):
    return re.sub(r'("durationSeconds": )\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', r'\1"<duration>"', text)


class MutationRunParity(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "src").mkdir()
        self.original = b"value = 1 < 2\n"
        (self.root / "src/example.py").write_bytes(self.original)
        (self.root / "src/other.py").write_bytes(self.original)
        (self.root / "outside.py").write_bytes(self.original)
        self.configure()
        self.file_limit = False

    def configure(self, command=None, timeout=300):
        self.settings = {"mutations": {"rules": ["comparison.less-to-less-equal"], "targets": {
            "unit": {"sources": ["src/example.py"], "command": command or [sys.executable, "-c", "print('tested')"],
                     "timeoutSeconds": timeout},
            "shared": {"sources": ["src/*.py"], "command": [sys.executable, "-c", "print('shared')"]},
        }}}
        self.save_config()

    def save_config(self):
        (self.root / "atlas.json").write_text(json.dumps(self.settings))

    def invoke(self, implementation, arguments, terminal_input=None):
        prefix = [str(RUST)] if implementation == "rust" else [sys.executable, str(REFERENCE), "cli"]
        environment = {**os.environ, "DATABASE_PATH": str(self.root / "graph.sqlite"), "COLUMNS": "80"}
        if terminal_input is None:
            return subprocess.run([*prefix, *arguments], cwd=self.root, env=environment, input="", capture_output=True,
                                  text=True, timeout=30, check=False, preexec_fn=limit_file_size if self.file_limit else None)
        master, slave = pty.openpty()
        try:
            with subprocess.Popen([*prefix, *arguments], cwd=self.root, env=environment, stdin=slave,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                os.write(master, terminal_input.encode())
                stdout, stderr = process.communicate(timeout=30)
                return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        finally:
            os.close(master)
            os.close(slave)

    def artifacts(self, filename):
        output = self.root / filename
        if not output.exists():
            return None
        logs = {path.name: path.read_bytes() for path in output.with_name(output.name + ".logs").iterdir()}
        return record_mask(output.read_text()), logs

    def compare(self, arguments, filename="mutation-results.jsonl", terminal_input=None):
        expected = self.invoke("python", arguments, terminal_input)
        artifacts = self.artifacts(filename)
        actual = self.invoke("rust", arguments, terminal_input)
        self.assertEqual(actual.returncode, expected.returncode, (actual.stderr, expected.stderr))
        self.assertEqual(actual.stdout, expected.stdout)
        self.assertEqual(duration_mask(actual.stderr), duration_mask(expected.stderr))
        self.assertEqual(self.artifacts(filename), artifacts)
        self.assertEqual((self.root / "src/example.py").read_bytes(), self.original)
        self.assertEqual((self.root / "src/other.py").read_bytes(), self.original)
        return actual

    def test_help_and_argument_errors(self):
        for arguments in [["mutations", "--help"], ["mutations", "run", "--help"],
                          ["mutations", "--rules", "run"], ["mutations", "run", "--f", "."],
                          ["mutations", "run", "--saved"], ["mutations", "run", "--target"],
                          ["mutations", "run", "extra"], ["mutations", "missing"],
                          ["mutations", "--", "--help"], ["mutations", "--", "--help", "--bogus"],
                          ["mutations", "--", "--saved"], ["mutations", "--folder", "--help", "run", "--help"]]:
            with self.subTest(arguments=arguments):
                self.compare(arguments)

    def test_target_errors_precede_analysis(self):
        for target in [None, "", "unit,", "all,unit", "missing", "z,a"]:
            with self.subTest(target=target):
                self.compare(["mutations", "run", *([] if target is None else ["--target", target])])

    def test_interactive_selection_retry_and_eof(self):
        for answer in ["unit\n", "all\n", "missing\nunit\n", "all,unit\nshared\n", "\nunit\n", "\x04"]:
            with self.subTest(answer=answer):
                self.compare(["mutations", "run"], terminal_input=answer)

    def test_target_selection_and_parent_folder(self):
        for target in ["unit", "all", " shared,unit,shared "]:
            with self.subTest(target=target):
                self.compare(["mutations", "--folder", str(self.root), "run", "--target", target])

    def test_outcomes_and_overwrite(self):
        for code in [0, 1, 7]:
            self.configure([sys.executable, "-c", f"print('exit {code}'); raise SystemExit({code})"])
            result = self.compare(["mutations", "run", "-f", str(self.root), "--target", "unit", "--output", "custom.jsonl"],
                                  "custom.jsonl")
            self.assertEqual(json.loads(result.stdout)["counts"], {"survived" if code == 0 else "killed": 1})

    def test_timeout_and_missing_executable(self):
        self.configure([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
        self.compare(["mutations", "run", "--target", "unit"])
        self.configure(["/nonexistent-atlas-command"])
        self.compare(["mutations", "run", "--target", "unit"])

    def test_empty_rules_and_unmatched_targets(self):
        self.settings["mutations"]["rules"] = []
        self.save_config()
        self.compare(["mutations", "run", "--target", "all"])
        self.configure()
        self.settings["mutations"]["targets"]["unit"]["sources"] = ["missing/**"]
        self.save_config()
        self.compare(["mutations", "run", "--target", "unit"])

    def test_saved_selection_and_stale_unselected_source(self):
        from atlas.persistence.database import migrate_database
        migrate_database(self.root / "graph.sqlite")
        indexed = self.invoke("python", ["index"])
        self.assertEqual(indexed.returncode, 0, indexed.stderr)
        (self.root / "outside.py").write_text("changed = 3 < 4\n")
        self.compare(["mutations", "--saved", "run", "--target", "unit"])
        (self.root / "src/example.py").write_text("changed = 3 < 4\n")
        self.original = (self.root / "src/example.py").read_bytes()
        # Stale sources fail before opening output. The other source stays unchanged.
        expected = self.invoke("python", ["mutations", "--saved", "run", "--target", "unit"])
        actual = self.invoke("rust", ["mutations", "--saved", "run", "--target", "unit"])
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                         (expected.returncode, expected.stdout, expected.stderr))

    def interrupted(self, implementation, signum):
        prefix = [str(RUST)] if implementation == "rust" else [sys.executable, str(REFERENCE), "cli"]
        ready = self.root / "ready"
        ready.unlink(missing_ok=True)
        with subprocess.Popen([*prefix, "mutations", "run", "--target", "unit"], cwd=self.root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            deadline = time.monotonic() + 15
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "Mutation command did not start")
            process.send_signal(signum)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 1, stderr)
            self.assertEqual((self.root / "src/example.py").read_bytes(), self.original)
            return stdout, duration_mask(stderr), self.artifacts("mutation-results.jsonl")

    def test_interrupt_output_and_source_restoration(self):
        self.configure([sys.executable, "-c", "from pathlib import Path; import time; Path('ready').touch(); time.sleep(30)"])
        for signum in [signal.SIGINT, signal.SIGTERM]:
            with self.subTest(signal=signum):
                self.assertEqual(self.interrupted("python", signum), self.interrupted("rust", signum))

    def test_invalid_glob_ranges(self):
        for pattern in ["src/[a--!]xample.py", "src/[z-a]xample.py", "src/[!z-a]xample.py", "src/[a-b-c]xample.py"]:
            with self.subTest(pattern=pattern):
                self.settings["mutations"]["targets"]["unit"]["sources"] = [pattern]
                self.save_config()
                self.compare(["mutations", "run", "--target", "unit"])

    def test_nul_command_argument_aborts(self):
        self.configure([sys.executable, "-c", "print(1)", "\u0000"])
        result = self.compare(["mutations", "run", "--target", "unit"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error: embedded null byte", result.stderr)

    def test_result_write_error(self):
        self.file_limit = True
        self.compare(["mutations", "run", "--target", "unit"])

    def test_output_and_working_directory_errors(self):
        self.compare(["mutations", "run", "--target", "unit", "--output", "missing/result.jsonl"], "unused.jsonl")
        (self.root / "result.jsonl.logs").touch()
        self.compare(["mutations", "run", "--target", "unit", "--output", "result.jsonl"], "unused.jsonl")
        self.settings["mutations"]["targets"]["unit"]["cwd"] = "missing"
        self.save_config()
        self.compare(["mutations", "run", "--target", "unit"], "unused.jsonl")

    def test_unicode_paths_and_target_names(self):
        old = self.root
        self.root = old / "café-😀"
        self.root.mkdir()
        for path in list(old.iterdir()):
            if path != self.root:
                path.rename(self.root / path.name)
        self.settings["mutations"]["targets"]["unité-😀"] = self.settings["mutations"]["targets"].pop("unit")
        self.save_config()
        self.compare(["mutations", "run", "--target", "all"])

    def test_invalid_target_configuration(self):
        for field, value in [("sources", []), ("sources", ["../outside"]), ("sources", ["/absolute"]),
                             ("sources", ["a\\b"]), ("sources", [" "]), ("command", []), ("command", [" "]),
                             ("timeoutSeconds", 0), ("timeoutSeconds", True), ("timeoutSeconds", 1.5),
                             ("timeoutSeconds", "2"), ("cwd", 5), ("unknown", True)]:
            with self.subTest(field=field, value=value):
                self.configure()
                self.settings["mutations"]["targets"]["unit"][field] = value
                self.save_config()
                self.compare(["mutations", "run", "--target", "all"])
        for name in ["all", "unit,other", " unit", ""]:
            with self.subTest(name=name):
                self.configure()
                self.settings["mutations"]["targets"][name] = self.settings["mutations"]["targets"].pop("unit")
                self.save_config()
                self.compare(["mutations", "run", "--target", "all"])

    def test_no_targets_and_protected_output(self):
        self.compare(["mutations", "run", "--target", "unit", "--output", "atlas.json"], "unused.jsonl")
        self.settings["mutations"]["targets"] = {}
        self.save_config()
        self.compare(["mutations", "run", "--target", "all"])


if __name__ == "__main__":
    unittest.main()
