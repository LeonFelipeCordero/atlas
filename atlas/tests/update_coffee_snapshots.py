"""Explicit regeneration: uv run python -m tests.update_coffee_snapshots."""

import json

from tests.coffee_fixture import LANGUAGES, SNAPSHOT_ROOT, coffee_graph, coffee_snapshot


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


if __name__ == "__main__":
    main()
