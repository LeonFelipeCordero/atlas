"""Normalize only runtime metadata; preserve source identities and evidence."""

import json
from pathlib import Path
from typing import Any

SNAPSHOTS = Path(__file__).parent / "snapshots" / "mutation" / "cli"


class MutationSnapshots:
    def __init__(self, root: Path) -> None:
        self.replacements = {str(root): "<project>"}
        self.trials: dict[str, str] = {}

    def capture(self, value: dict[str, Any]) -> None:
        for key in ("session_id", "created_at", "recorded_at"):
            if key in value:
                self.replacements[value[key]] = f"<{key}>"
        if "trial_id" in value:
            trial_id = value["trial_id"]
            self.trials.setdefault(trial_id, f"<trial-{len(self.trials) + 1}>")
            self.replacements[trial_id] = self.trials[trial_id]
        for trial in value.get("trials", []):
            self.capture(trial)

    def check(self, name: str, output: str, *, markdown: bool = False) -> None:
        if not markdown:
            self.capture(json.loads(output))
        for original, replacement in self.replacements.items():
            output = output.replace(original, replacement)
        actual = output if markdown else json.loads(output)
        path = SNAPSHOTS / f"{name}.{'md' if markdown else 'json'}"
        expected = path.read_text() if markdown else json.loads(path.read_text())
        assert actual == expected
