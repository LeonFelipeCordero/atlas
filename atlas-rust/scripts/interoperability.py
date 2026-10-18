"""Read the same Python-produced and Rust-produced databases with both runtimes."""
from __future__ import annotations

from dataclasses import replace

from cases import Case, navigation_cases
from common import SAMPLES, Process
from database import backup, keys, revision, uuid_fixture
from navigation import labels
from project import Project


def reader(case: Case) -> bool:
    return case.name.startswith("graph.") or case.name in {"projects", "mutations.saved"}


def canonical_selected(project) -> bool:
    if project.root.parent != SAMPLES:
        return False
    return any(project.run.selected(Case("navigation." + label, ())) for label in labels(project.root))


def produce(project) -> Project | None:
    native = project.folder / "native-origin.sqlite"
    backup(project.baseline, native)
    command = [str(project.run.args.rust_bin), "index", "-f", str(project.root)]
    result = Process(command, project.root, native, project.run.args.timeout).run()
    if result["exit_code"] != 0 or result["timeout"]:
        project.run.save({"project": str(project.root), "case": "setup.native.index", "phase": "setup", "passed": False,
                          "rust": result, "error": "Native-origin graph cases are blocked"})
        return None
    if uuid_fixture(native) is None:
        raise ValueError("Rust interop producer did not save a graph revision")
    context = Project(project.run, project.root, project.folder)
    context.baseline = native
    return context


def native_case(case: Case, revisions: tuple[str | None, str | None]) -> Case:
    original, native = revisions
    if native is None:
        raise ValueError("Native-origin graph has no revision")
    arguments = case.args
    if case.name == "graph.revision.valid":
        arguments = tuple(native if argument == original else argument for argument in arguments)
    return replace(case, name="interop.native." + case.name, args=arguments)


def compare(project, cases: list[Case]) -> None:
    readers = list(filter(reader, cases))
    if project.run.exhausted() or not (readers or canonical_selected(project)):
        return
    native = produce(project)
    if native is None:
        block_readers(project, readers)
        return
    if not project.ready():
        readers = available_readers(native, readers)
    revisions = revision(project.baseline), revision(native.baseline)
    for case in readers:
        native.run_case(native_case(case, revisions))
    native.canonical("interop.native.")


def available_readers(native, readers: list[Case]) -> list[Case]:
    graph = navigation_cases(native.root, keys(native.baseline), revision(native.baseline) or "")
    return [case for case in readers if not case.name.startswith("graph.")] + list(filter(native.run.selected, graph))


def block_readers(project, readers: list[Case]) -> None:
    for case in readers:
        project.blocked(Case("interop.native." + case.name, ()), "native index failed or timed out")
