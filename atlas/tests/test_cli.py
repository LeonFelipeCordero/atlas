import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from atlas.cli import main
from atlas.bootstrap import repository_service


class CliTest(unittest.TestCase):
    def test_help_lists_commands_without_project_selector(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        for command in ("index", "projects", "report"):
            self.assertIn(command, result.output)
        self.assertNotIn("migrate", result.output)
        self.assertNotIn("serve", result.output)
        self.assertNotIn("--project", result.output)
        self.assertNotIn("--database", result.output)

    def test_migrate_is_not_a_cli_command(self) -> None:
        result = CliRunner().invoke(main, ["migrate"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("No such command", result.output)
        self.assertIn("migrate", result.output)

    def test_migration_script_and_index_current_directory_without_json_file(self) -> None:
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "main.py").write_text("def main():\n    return 1\n")
            database = root / "db" / "index.sqlite"
            runner = CliRunner(env={"DATABASE_PATH": str(database)})
            migrated = subprocess.run(
                ["atlas-migrate"],
                env={**os.environ, "DATABASE_PATH": str(database)},
                capture_output=True, text=True,
            )
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            with repository_service(database) as service:
                registered = service.register({"name": "example", "location": str(source)})
            try:
                os.chdir(source)
                result = runner.invoke(main, ["index"])
            finally:
                os.chdir(original_directory)
            self.assertEqual(result.exit_code, 0, result.output)
            summary = json.loads(result.output)
            self.assertEqual(summary["repositoryId"], registered.id)
            self.assertEqual(summary["schemaVersion"], 2)
            self.assertEqual(summary["stats"]["files"], 1)
            self.assertEqual(sorted(path.name for path in source.iterdir()), ["main.py"])
            with repository_service(database) as service:
                saved = service.get_architecture(registered.id)
                assert saved is not None
                self.assertEqual(saved.artifact["stats"], summary["stats"])


if __name__ == "__main__":
    unittest.main()
