import json
import os
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from atlas.cli import main
from atlas.bootstrap import repository_service


class CliTest(unittest.TestCase):
    def test_help_lists_commands_and_project_is_required(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        for command in ("index", "migrate", "projects", "report"):
            self.assertIn(command, result.output)
        self.assertNotIn("serve", result.output)
        missing = runner.invoke(main, ["index"])
        self.assertNotEqual(missing.exit_code, 0)
        self.assertIn("--project", missing.output)

    def test_migrate_and_index_current_directory_without_json_file(self) -> None:
        runner = CliRunner()
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "main.py").write_text("def main():\n    return 1\n")
            database = root / "db" / "index.sqlite"
            migrated = runner.invoke(main, ["migrate", "--database", str(database)])
            self.assertEqual(migrated.exit_code, 0, migrated.output)
            with repository_service(database) as service:
                registered = service.register({"name": "example", "location": str(source)})
            try:
                os.chdir(source)
                result = runner.invoke(main, ["index", "--project", "example", "--database", str(database)])
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
