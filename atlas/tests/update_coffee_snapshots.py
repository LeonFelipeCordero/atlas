"""Regenerate every seam from the shared coffee projects; optionally navigation."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.coffee_fixture import BREWING_LANGUAGES, LANGUAGES, SNAPSHOT_ROOT
from tests.coffee_navigation import NAVIGATION_SNAPSHOT_ROOT, navigation_responses
from tests.coffee_pipeline import coffee_pipeline, write_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation", action="store_true", help="Also regenerate saved graph CLI output")
    options = parser.parse_args()
    for language in LANGUAGES:
        bundle = coffee_pipeline(language)
        write_pipeline(language)
        (SNAPSHOT_ROOT / f"{language}-coffee.json").write_text(
            json.dumps(bundle["graph"], ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        write_markdown(language, bundle["cli"])
        print(language)
        if options.navigation and language in BREWING_LANGUAGES:
            write_navigation(language)


def write_markdown(language, outputs):
    for command in ("report", "check"):
        (SNAPSHOT_ROOT / f"{language}-coffee-{command}.md").write_text(
            outputs[f"{command}-markdown"]["output"], encoding="utf-8",
        )


def write_navigation(language):
    with TemporaryDirectory() as directory:
        navigation = navigation_responses(language, Path(directory) / "atlas.sqlite")
    NAVIGATION_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    (NAVIGATION_SNAPSHOT_ROOT / f"{language}-coffee.json").write_text(
        json.dumps(navigation, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
