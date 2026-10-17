"""Replay unchanged Python coffee scenarios; compare raw responses without UUID masking."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from cases import Case
from common import REPO, SNAPSHOTS, require

if TYPE_CHECKING:
    from project import Project

sys.path.insert(0, str(REPO / "atlas"))
CoffeeNavigation = import_module("tests.coffee_navigation").CoffeeNavigation


def labels(root: Path) -> list[str]:
    path = SNAPSHOTS / "coffee" / root.name / "navigation.json"
    return list(json.loads(path.read_text())) if path.exists() else []


@dataclass
class Replay(CoffeeNavigation):
    harness: Project | None = None
    prefix: str = ""

    def context(self) -> Project:
        if self.harness is None:
            raise ValueError("Navigation replay requires a project context")
        return self.harness

    def matches(self, label: str) -> bool:
        harness = self.context()
        return (harness.run.selected(Case("navigation." + label, ())) or
                harness.run.selected(Case(self.prefix + "navigation." + label, ())))

    def query(self, label: str, *arguments: str) -> dict:
        command = ("graph", "--project", self.project, *arguments)
        harness = self.context()
        result = harness.oracle(["cli", *command])
        require(result, f"Reference navigation {label}")
        payload = json.loads(result["stdout"])
        self.responses[label] = payload
        if self.matches(label):
            harness.run_case(Case(self.prefix + "navigation." + label, command))
        return payload

    def execute(self) -> None:
        self.query("overview", "overview")
        for name in ("find_core", "select_core", "show_render", "calls"):
            getattr(self, name)()
        self.source("source_render", self.selected["render"])
        for name in ("imports", "inheritance", "callback", "recursion"):
            getattr(self, name)()
        # Do not call collect(): its aggregate normalizer masks UUIDs.


def replay(project: Project, prefix: str = "") -> None:
    # The dynamically loaded reference dataclass supplies the inherited constructor fields.
    scenario: Replay = cast(Any, Replay)(project.root, project.root.name, harness=project, prefix=prefix)
    if any(scenario.matches(label) for label in labels(project.root)):
        scenario.execute()
