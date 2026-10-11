import unittest
from click.testing import CliRunner

from atlas.cli import main


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


if __name__ == "__main__":
    unittest.main()
