"""Explicit regeneration: uv run python -m tests.update_coffee_snapshots."""

import json

from click.testing import CliRunner

from atlas.cli import main as cli
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT, coffee_graph, coffee_snapshot


def main() -> None:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    for language in LANGUAGES:
        path = SNAPSHOT_ROOT / f"{language}-coffee.json"
        snapshot = coffee_snapshot(coffee_graph(language))
        path.write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(path.name)
        report = CliRunner().invoke(cli, [
            "report", "--folder", str(FIXTURE_ROOT / language),
        ])
        if report.exit_code != 0:
            raise RuntimeError(f"{language} report failed: {report.output}")
        report_path = SNAPSHOT_ROOT / f"{language}-coffee-report.md"
        report_path.write_text(report.output, encoding="utf-8")
        print(report_path.name)
        check = CliRunner().invoke(cli, [
            "check", "--folder", str(FIXTURE_ROOT / language),
        ])
        if check.exit_code != 1 or not isinstance(check.exception, SystemExit) or not check.output.startswith("## "):
            raise RuntimeError(f"{language} check failed: {check.output}") from check.exception
        check_path = SNAPSHOT_ROOT / f"{language}-coffee-check.md"
        check_path.write_text(check.output, encoding="utf-8")
        print(check_path.name)


if __name__ == "__main__":
    main()
