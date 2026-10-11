"""Regenerate graph/report/check snapshots; add --navigation for graph CLI output."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from atlas.cli import main as cli
from tests.coffee_fixture import FIXTURE_ROOT, LANGUAGES, SNAPSHOT_ROOT, coffee_graph, coffee_snapshot
from tests.coffee_navigation import NAVIGATION_SNAPSHOT_ROOT, navigation_responses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation", action="store_true", help="Also regenerate production-indexed graph navigation snapshots")
    options = parser.parse_args()
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
        if options.navigation:
            with TemporaryDirectory() as directory:
                navigation = navigation_responses(language, Path(directory) / "atlas.sqlite")
            NAVIGATION_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
            navigation_path = NAVIGATION_SNAPSHOT_ROOT / f"{language}-coffee.json"
            navigation_path.write_text(
                json.dumps(navigation, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            print(navigation_path.relative_to(SNAPSHOT_ROOT))


if __name__ == "__main__":
    main()
