"""Opt-in sample-only configuration and stale-source cases. Never edit reference fixtures."""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from cases import Case
from common import SNAPSHOTS
from project import Project


def rules() -> list[str]:
    return sorted({mutation["ruleId"] for path in (SNAPSHOTS / "mutations").glob("*-operators.json")
                   for mutation in json.loads(path.read_text())["mutations"]})


def definitions() -> list[tuple[str, str, str]]:
    enabled = json.dumps({"mutations": {"rules": rules()}})
    result = [("enabled", enabled, ""), ("operators", enabled, ""),
              ("disabled", '{"mutations":{"rules":[]}}', ""),
              ("duplicates", json.dumps({"mutations": {"rules": rules() * 2}}), ""),
              ("stale", enabled, "change"), ("deleted", enabled, "delete"), ("symlink", enabled, "symlink")]
    invalid = ["{", "[]", '{"unknown":1}', '{"maxParameters":-1}', '{"maxParameters":"3"}',
               '{"maxInstability":2}', '{"mutations":{"rules":{"arithmetic.add-to-subtract":"-"}}}',
               '{"mutations":{"rules":["unknown"]}}']
    result.extend((f"invalid-{index}", text, "invalid") for index, text in enumerate(invalid))
    result.extend([("checks-disabled", json.dumps({key: None for key in (
        "maxFileLines", "maxFunctionLines", "maxParameters", "maxWeightedComplexity", "maxDecisionDepth",
        "maxChangeImpact", "maxInstability", "maxCircularImportGroups", "maxNestedLoops")}), "check"),
                   ("checks-dependencies", '{"maxChangeImpact":0,"maxInstability":0.4}', "check")])
    return result


def variant_cases(name: str, root: Path, change: str) -> list[Case]:
    if change == "invalid":
        return [Case(f"mutations.variant.{name}", ("mutations", "-f", str(root)), valid=False),
                Case(f"check.variant.{name}", ("check", "-f", str(root), "--save", "--format", "json"), True, valid=False)]
    if change == "check":
        return [Case(f"check.variant.{name}.{format}", ("check", "-f", str(root), "--format", format)) for format in ("json", "markdown")]
    return [Case(f"mutations.variant.{name}.{mode}", ("mutations", "-f", str(root)) + (("--saved",) if mode == "saved" else ()),
                 valid=not change) for mode in ("fresh", "saved")]


def alter_source(root: Path, baseline: Path, change: str) -> None:
    if change not in {"change", "delete", "symlink"}:
        return
    with sqlite3.connect(baseline) as database:
        path = database.execute("SELECT path FROM graph_mutation_candidates ORDER BY ordinal LIMIT 1").fetchone()
    if path is None:
        raise RuntimeError("Sample has no mutation candidates for stale-source variant")
    source = root / path[0]
    content = source.read_bytes()
    if change == "change":
        source.write_bytes(b"// changed\n" + content)
    elif change == "delete":
        source.unlink()
    else:
        outside = root.parent / "outside-source"
        outside.write_bytes(content)
        source.unlink()
        source.symlink_to(outside)


def run_variants(project) -> None:
    for definition in definitions():
        if project.run.exhausted():
            return
        if variant_selected(project, definition):
            run_variant(project, definition)


def variant_selected(project, definition: tuple[str, str, str]) -> bool:
    name, _, change = definition
    return any(project.run.selected(case) for case in variant_cases(name, project.root, change))


def run_variant(project, definition: tuple[str, str, str]) -> None:
    with tempfile.TemporaryDirectory(prefix="variant-", dir=project.folder) as temporary:
        variant = prepare_variant(project, definition, Path(temporary))
        name, _, change = definition
        for case in filter(project.run.selected, variant_cases(name, variant.root, change)):
            variant.run_case(case)


def prepare_variant(project, definition: tuple[str, str, str], work: Path) -> Project:
    name, config, change = definition
    source = project.root
    original = source.parent / "mutations" / source.name if name == "operators" else source
    root = work / source.name
    shutil.copytree(original, root, ignore=shutil.ignore_patterns("__pycache__"))
    variant = Project(project.run, root, work)
    variant.prepare()
    (root / "atlas.json").write_text(config)
    alter_source(root, variant.baseline, change)
    return variant
