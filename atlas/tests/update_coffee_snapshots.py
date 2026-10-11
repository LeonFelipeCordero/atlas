"""Regenerate every seam from the shared coffee projects; optionally navigation."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.coffee_fixture import BREWING_LANGUAGES, LANGUAGES
from tests.coffee_navigation import NAVIGATION_SNAPSHOT_ROOT, navigation_responses
from tests.coffee_pipeline import write_pipeline
from tests.variant_snapshot_support import write_variants


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation", action="store_true", help="Also regenerate saved graph CLI output")
    options = parser.parse_args()
    for language in LANGUAGES:
        write_pipeline(language)
        print(language)
        if options.navigation and language in BREWING_LANGUAGES:
            write_navigation(language)
    write_variants()


def write_navigation(language):
    with TemporaryDirectory() as directory:
        navigation = navigation_responses(language, Path(directory) / "atlas.sqlite")
    NAVIGATION_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    (NAVIGATION_SNAPSHOT_ROOT / language / "navigation.json").write_text(
        json.dumps(navigation, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
