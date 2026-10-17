"""CLI matrix derived from atlas/tests/cli and the coffee navigation scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import chain, product
from pathlib import Path


@dataclass(frozen=True)
class Case:
    name: str
    args: tuple[str, ...]
    writes: bool = False
    migration: bool = False
    valid: bool = True


def folder_cases(root: Path) -> list[Case]:
    result = []
    for action, alias in product(("index", "report", "check", "mutations"), (None, "-f", "--f", "--folder")):
        arguments = (action,) + ((alias, str(root)) if alias else ())
        result.append(Case(f"{action}.folder.{alias or 'default'}", arguments, action == "index"))
    return result


def format_cases(root: Path) -> list[Case]:
    result = []
    for action, format, save in product(("report", "check"), (None, "json", "markdown"), (False, True)):
        arguments = (action, "-f", str(root)) + (("--format", format) if format else ()) + (("--save",) if save else ())
        result.append(Case(f"{action}.{format or 'default'}.{'save' if save else 'fresh'}", arguments, save))
    return result


def analysis_cases(root: Path) -> list[Case]:
    return [Case("projects", ("projects",)), *folder_cases(root), *format_cases(root),
            Case("mutations.rules", ("mutations", "--rules")),
            Case("mutations.saved", ("mutations", "--saved", "-f", str(root))),
            Case("migrate.fresh", (), True, True), Case("migrate.repeat", (), True, True), *option_cases(root)]


def option_cases(root: Path) -> list[Case]:
    return [Case("report.folder.attached", ("report", f"-f{root}", "--format=json")),
            Case("mutations.folder.attached", ("mutations", f"-f{root}")),
            Case("projects.group.terminator", ("--", "projects")),
            Case("report.help.folder.value", ("report", "--folder", "--help"), valid=False),
            Case("report.help.format.value", ("report", "--format", "--help"), valid=False),
            Case("mutations.help.folder.value", ("mutations", "--folder", "--help"), valid=False),
            Case("mutations.help.literal", ("mutations", "--", "--help"), valid=False)]


def navigation_cases(root: Path, keys: tuple[str, str, str, str], revision: str) -> list[Case]:
    repository, file, first, second = keys
    prefix = ("graph", "--project", root.name)
    queries = [("overview",), ("find", "brew"), ("find", "café", "--limit", "100"),
               ("find", first, "--limit", "1"), ("show", first), ("children", file),
               ("children", repository, "--limit", "1", "--offset", "1"),
               ("children", file, "--limit", "100", "--offset", "200"),
               ("context", first), ("path", first, second)]
    result = [Case(f"graph.{arguments[0]}.default.{index}", prefix + arguments) for index, arguments in enumerate(queries)]
    result.extend(traversal_cases((prefix, first, second)))
    result.extend(source_cases((prefix, first, second)))
    result.extend(numeric_cases((prefix, file, first)))
    result.extend([Case("graph.source.default", prefix + ("source", first)),
                   Case("graph.source.unavailable", prefix + ("source", "external:missing"), valid=False),
                   Case("graph.project.cwd", ("graph", "overview")),
                   Case("graph.project.id", ("graph", "--project", "00000000-0000-4000-8000-000000000001", "overview")),
                   Case("graph.revision.valid", prefix + ("--revision", revision, "overview")),
                   Case("graph.revision.stale", prefix + ("--revision", "stale", "overview"), valid=False),
                   Case("graph.project.missing", ("graph", "--project", "missing", "overview"), valid=False),
                   Case("graph.group.terminator", prefix + ("--", "overview")),
                   Case("graph.group.root.terminator", ("--", "graph", "--", "overview")),
                   Case("graph.find.literal.help", prefix + ("find", "--", "--help"))])
    return result


def numeric_cases(selection: tuple) -> list[Case]:
    prefix, file, first = selection
    huge = "1" + "0" * 99
    result = [Case("graph.numeric.find.decimal", prefix + ("find", first, "--limit", " 1_0 ")),
              Case("graph.numeric.find.math", prefix + ("find", first, "--limit", "𝟙𝟘")),
              Case("graph.numeric.children.decimal", prefix + ("children", file, "--offset", "١_٠")),
              Case("graph.numeric.context.fullwidth", prefix + ("context", first, "--depth", "２")),
              Case("graph.numeric.source.huge.json", prefix + ("source", first, "--start-line", huge, "--format", "json")),
              Case("graph.numeric.source.huge.text", prefix + ("source", first, "--start-line", huge, "--format", "text"))]
    invalid = [("double-underscore", "1__0"), ("non-decimal", "²"), ("hexadecimal", "0x10"), ("overflow", "9" * 100)]
    result.extend(Case(f"graph.numeric.invalid.limit.{name}", prefix + ("find", first, "--limit", value), valid=False)
                  for name, value in invalid)
    return result


def traversal_cases(selection: tuple) -> list[Case]:
    prefix, first, second = selection
    result = []
    combinations = product(("context", "path"), ("out", "in", "both"), ((0, 1, 1), (20, 300, 1000)),
                           ("CALLS", "REFERENCES", "IMPORTS", "INHERITS", "CONTAINS", " references, calls, CALLS, ,inherits, imports,contains "))
    for command, direction, limits, relations in combinations:
        depth, nodes, edges = limits
        arguments = (command, first) + ((second,) if command == "path" else ())
        arguments += ("--max-depth" if command == "path" else "--depth", str(depth), "--direction", direction,
                      "--relations", relations, "--max-nodes", str(nodes), "--max-edges", str(edges))
        result.append(Case(f"graph.{command}.{direction}.{depth}.{relations}", prefix + arguments))
    return result


def source_cases(selection: tuple) -> list[Case]:
    prefix, first, second = selection
    result = []
    for multiple, format, bounded in product((False, True), ("json", "text"), (False, True)):
        arguments = ("source", first) + ((second, first) if multiple else ()) + ("--format", format)
        arguments += ("--max-lines", "1", "--start-line", "1") if bounded else ("--max-lines", "500", "--start-line", "7")
        result.append(Case(f"graph.source.{multiple}.{format}.{bounded}", prefix + arguments))
    return result


def help_cases() -> list[Case]:
    groups = [(), ("index",), ("projects",), ("report",), ("check",), ("mutations",), ("graph",)]
    groups += [("graph", command) for command in ("overview", "find", "show", "children", "context", "source", "path")]
    return [Case("help." + (".".join(group) or "atlas"), group + ("--help",)) for group in groups]


def expand_invalid(definition: tuple) -> list[Case]:
    command, option, values = definition
    return [Case(f"invalid.{command[0]}.{option}.{value}", ("graph",) + command + (option, value), valid=False) for value in values]


def invalid_bounds() -> list[Case]:
    definitions = [(("find", "brew"), "--limit", ("0", "101", "many")),
                   (("children", "brew"), "--limit", ("0", "101", "many")),
                   (("children", "brew"), "--offset", ("-1", "many")),
                   (("context", "brew"), "--depth", ("-1", "21", "many")),
                   (("path", "brew", "serve"), "--max-depth", ("-1", "21", "many")),
                   (("source", "brew"), "--max-lines", ("0", "501", "many")),
                   (("source", "brew"), "--start-line", ("0", "many")),
                   (("source", "brew"), "--format", ("yaml", "JSON"))]
    return list(chain.from_iterable(map(expand_invalid, definitions)))


def invalid_traversal_definition(combination: tuple) -> tuple:
    command, option = combination
    values = {"--direction": ("sideways", "OUT"), "--relations": ("", " , , ", "CALLS,BOGUS", "CALL"),
              "--max-nodes": ("0", "301", "many"), "--max-edges": ("0", "1001", "many")}
    arguments = (command, "brew") + (("serve",) if command == "path" else ())
    return arguments, option, values[option]


def invalid_usage() -> list[Case]:
    missing = [("find",), ("show",), ("children",), ("context",), ("source",), ("path",), ("path", "brew"),
               ("overview", "extra"), ("overview", "--project", "coffee"), ("unknown",)]
    return [Case("invalid.usage." + ".".join(arguments), ("graph",) + arguments, valid=False) for arguments in missing]


def usage_cases() -> list[Case]:
    combinations = product(("context", "path"), ("--direction", "--relations", "--max-nodes", "--max-edges"))
    traversals = chain.from_iterable(map(expand_invalid, map(invalid_traversal_definition, combinations)))
    formats = [Case(f"invalid.{action}.format", (action, "--format", "yaml"), valid=False) for action in ("report", "check")]
    literal = [Case("help.group.terminator", ("--", "--help")),
               Case("help.graph.group.selector", ("graph", "--", "--project", "missing", "--help")),
               Case("invalid.group.help.trailing.flag", ("--", "--help", "--bogus"), valid=False),
               Case("invalid.graph.group.help.trailing.value", ("graph", "--", "--help", "--project"), valid=False),
               Case("invalid.group.option.command", ("--", "--bogus"), valid=False),
               Case("invalid.graph.group.option.command", ("graph", "--", "--project", "missing"), valid=False),
               Case("invalid.command.suggest.root", ("reports",), valid=False),
               Case("invalid.command.suggest.graph", ("graph", "contexts"), valid=False),
               Case("invalid.command.suggest.unicode", ("réports",), valid=False)]
    return help_cases() + invalid_bounds() + list(traversals) + invalid_usage() + formats + literal
