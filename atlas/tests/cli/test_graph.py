"""Exercise real graph dispatch and rendering without opening an index."""

import json
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from atlas.cli import main
from atlas.domain.navigation import NavigationError, PathRequest, TraversalRequest
from atlas.services.navigation import NavigationService


@pytest.fixture
def navigation():
    with patch("atlas.cli.graph.navigation_service") as boundary:
        service = MagicMock(spec=NavigationService)
        boundary.return_value.__enter__.return_value = service
        yield boundary, service


@pytest.mark.parametrize("case", [
    (["overview"], "overview", {}),
    (["find", "café"], "find", {"query": "café", "limit": 10}),
    (["find", "brew", "--limit", "100"], "find", {"query": "brew", "limit": 100}),
    (["show", "external:brew"], "show", {"key": "external:brew"}),
    (["children", "file:coffee.py"], "children", {"key": "file:coffee.py", "limit": 30, "offset": 0}),
    (["children", "root", "--limit", "1", "--offset", "200"], "children", {"key": "root", "limit": 1, "offset": 200}),
    (["context", "brew"], "context", {"request": TraversalRequest("brew", "out", ["CALLS", "REFERENCES"], 2, 30, 100)}),
    (["path", "brew", "serve"], "path", {"request": PathRequest("serve", TraversalRequest("brew", "out", ["CALLS", "REFERENCES"], 6, 30, 100))}),
    (["source", "brew"], "source", {"key": "brew", "max_lines": 80, "start_line": None}),
    (["source", "brew", "serve"], "sources", {"keys": ["brew", "serve"], "max_lines": 80, "start_line": None}),
    (["source", "brew", "--max-lines", "500", "--start-line", "7", "--format", "json"], "source", {"key": "brew", "max_lines": 500, "start_line": 7}),
    (["source", "serve", "brew", "serve", "--max-lines", "1", "--start-line", "1"], "sources", {"keys": ["serve", "brew", "serve"], "max_lines": 1, "start_line": 1}),
])
def test_dispatch_defaults_and_options(navigation, case):
    args, method, options = case
    boundary, service = navigation
    payload = {
        "repositoryId": "coffee", "graphRevision": "rev-1", "indexedAt": None,
        "filters": {}, "diagnostics": [{"message": "café"}], "diagnosticsTruncated": False,
    }
    getattr(service, method).return_value = payload

    result = CliRunner().invoke(main, ["graph", *args])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == payload
    assert "café" in result.stdout
    boundary.assert_called_once_with(None, None)
    assert service.mock_calls == [call.__getattr__(method)(**options)]
    boundary.return_value.__exit__.assert_called_once_with(None, None, None)


def test_project_and_revision_are_group_options(navigation):
    boundary, service = navigation
    service.overview.return_value = {"roots": []}
    result = CliRunner().invoke(main, ["graph", "--project", "coffee", "--revision", "rev-1", "overview"])
    assert result.exit_code == 0, result.output
    boundary.assert_called_once_with("coffee", "rev-1")
    service.overview.assert_called_once_with()


@pytest.mark.parametrize("route", [
    ("context", "out"), ("context", "in"), ("context", "both"),
    ("path", "out"), ("path", "in"), ("path", "both"),
])
@pytest.mark.parametrize("limits", [(0, 1, 1), (20, 300, 1000)])
def test_traversal_options_build_requests(navigation, route, limits):
    command, direction = route
    depth, nodes, edges = limits
    _, service = navigation
    getattr(service, command).return_value = {"nodes": [], "edges": []}
    args = [command, "external:brew"]
    if command == "path":
        args.append("serve")
    args += ["--depth" if command == "context" else "--max-depth", str(depth),
             "--direction", direction, "--relations", " references, calls, CALLS, ,inherits, imports,contains ",
             "--max-nodes", str(nodes), "--max-edges", str(edges)]

    result = CliRunner().invoke(main, ["graph", *args])

    assert result.exit_code == 0, result.output
    traversal = TraversalRequest("external:brew", direction, ["CALLS", "CONTAINS", "IMPORTS", "INHERITS", "REFERENCES"], depth, nodes, edges)
    request = PathRequest("serve", traversal) if command == "path" else traversal
    getattr(service, command).assert_called_once_with(request=request)


@pytest.mark.parametrize("case", [
    (["find", "brew"], "--limit", ["0", "101", "many"]),
    (["children", "brew"], "--limit", ["0", "101", "many"]),
    (["children", "brew"], "--offset", ["-1", "many"]),
    (["context", "brew"], "--depth", ["-1", "21", "many"]),
    (["path", "brew", "serve"], "--max-depth", ["-1", "21", "many"]),
    (["source", "brew"], "--max-lines", ["0", "501", "many"]),
    (["source", "brew"], "--start-line", ["0", "many"]),
    (["source", "brew"], "--format", ["yaml", "JSON"]),
])
def test_invalid_command_options_do_not_open_navigation(navigation, case):
    command, option, values = case
    boundary, _ = navigation
    for value in values:
        result = CliRunner().invoke(main, ["graph", *command, option, value])
        assert result.exit_code == 2, result.output
        assert f"Invalid value for '{option}'" in result.stderr
        assert result.stdout == ""
    boundary.assert_not_called()


@pytest.mark.parametrize("command", [["context", "brew"], ["path", "brew", "serve"]])
@pytest.mark.parametrize("option_value", [
    ("--direction", "sideways"), ("--direction", "OUT"),
    ("--relations", ""), ("--relations", " , , "),
    ("--relations", "CALLS,BOGUS"), ("--relations", "CALL"),
    ("--max-nodes", "0"), ("--max-nodes", "301"), ("--max-nodes", "many"),
    ("--max-edges", "0"), ("--max-edges", "1001"), ("--max-edges", "many"),
])
def test_invalid_traversal_options(navigation, command, option_value):
    option, value = option_value
    boundary, _ = navigation
    result = CliRunner().invoke(main, ["graph", *command, option, value])
    assert result.exit_code == 2, result.output
    assert f"Invalid value for '{option}'" in result.stderr
    if option == "--relations":
        assert "Choose comma-separated relations from CONTAINS, CALLS, REFERENCES, IMPORTS, INHERITS" in result.stderr
    boundary.assert_not_called()


@pytest.mark.parametrize(("args", "message"), [
    (["find"], "Missing argument 'QUERY'"),
    (["show"], "Missing argument 'KEY'"),
    (["children"], "Missing argument 'KEY'"),
    (["context"], "Missing argument 'KEY'"),
    (["source"], "Missing argument 'KEYS...'"),
    (["path"], "Missing argument 'FROM'"),
    (["path", "brew"], "Missing argument 'TO'"),
    (["overview", "extra"], "Got unexpected extra argument"),
    (["overview", "--project", "coffee"], "No such option '--project'"),
    (["unknown"], "No such command 'unknown'"),
])
def test_usage_errors(navigation, args, message):
    boundary, _ = navigation
    result = CliRunner().invoke(main, ["graph", *args])
    assert result.exit_code == 2, result.output
    assert message in result.stderr
    boundary.assert_not_called()


@pytest.mark.parametrize("command", [None, "overview", "find", "show", "children", "context", "source", "path"])
def test_help_does_not_open_navigation(navigation, command):
    boundary, _ = navigation
    result = CliRunner().invoke(main, ["graph", *([command] if command else []), "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout
    if command is None:
        for name in ("overview", "find", "show", "children", "context", "source", "path"):
            assert name in result.stdout
    boundary.assert_not_called()


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("output_format", ["json", "text"])
def test_source_output_contract(navigation, multiple, output_format):
    _, service = navigation
    excerpt = {
        "status": "ok", "path": "café.py", "startLine": 7, "endLine": 8,
        "lines": ["def café():", "    return 1"], "truncated": True, "nextStartLine": 9,
    }
    filters: dict[str, Any] = {"maxLines": 2, "startLine": 7}
    filters.update({"keys": ["brew", "external:serve"]} if multiple else {"key": "brew"})
    metadata = {"repositoryId": "coffee", "graphRevision": "rev-1", "indexedAt": None,
                "filters": filters, "diagnostics": [{"message": "café"}], "diagnosticsTruncated": True}
    excerpts = [{"stableKey": "brew", **excerpt}, {"stableKey": "external:serve", "status": "unavailable"}]
    details = excerpts[0].copy()
    details.pop("lines")
    payload = {**metadata, **({"sources": excerpts} if multiple else {"source": excerpt})}
    method = service.sources if multiple else service.source
    method.return_value = payload
    args = ["graph", "source", "brew", *(["external:serve"] if multiple else []),
            "--max-lines", "2", "--start-line", "7", "--format", output_format]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    if output_format == "json":
        assert json.loads(result.stdout) == payload
    else:
        expected = [json.dumps(metadata, ensure_ascii=False),
                    "\n".join(["### café.py", json.dumps(details, ensure_ascii=False),
                               "7: def café():", "8:     return 1"])]
        if multiple:
            expected.append('### external:serve\n{"stableKey": "external:serve", "status": "unavailable"}')
        assert result.stdout == "\n\n".join(expected) + "\n"
    options: dict[str, Any] = {"max_lines": 2, "start_line": 7}
    options.update({"keys": ["brew", "external:serve"]} if multiple else {"key": "brew"})
    method.assert_called_once_with(**options)


def test_cli_projects_unresolved_output_without_changing_stable_keys(navigation):
    _, service = navigation
    service.context.return_value = {
        "nodes": [{"stableKey": "external:brew", "level": "external", "type": "external",
                   "qualifiedName": "external:brew", "external": True}],
        "edges": [{"sourceStableKey": "serve", "targetStableKey": "external:brew", "type": "CALLS"}],
        "boundaries": [{"stableKey": "external:brew", "reason": "external_unresolved_or_ambiguous", "expandable": False}],
    }
    result = CliRunner().invoke(main, ["graph", "context", "serve"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "nodes": [{"stableKey": "external:brew", "level": "unresolved", "type": "unresolved",
                   "qualifiedName": "unresolved:brew", "external": False, "unresolved": True}],
        "edges": [{"sourceStableKey": "serve", "targetStableKey": "external:brew", "type": "CALLS"}],
        "boundaries": [{"stableKey": "external:brew", "reason": "unresolved_or_ambiguous", "expandable": False}],
    }


@pytest.mark.parametrize("error_type", [NavigationError, OSError, ValueError])
@pytest.mark.parametrize("stage", ["factory", "enter", "command", "exit"])
def test_navigation_errors_are_json_on_stderr(navigation, error_type, stage):
    boundary, service = navigation
    error = error_type('stale "café"\nreindex')
    service.overview.return_value = {"roots": []}
    target = {"factory": boundary, "enter": boundary.return_value.__enter__,
              "command": service.overview, "exit": boundary.return_value.__exit__}[stage]
    target.side_effect = error

    result = CliRunner().invoke(main, ["graph", "overview"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": str(error)}
    assert result.stderr.count("\n") == 1
    assert result.exception is not None


def test_unexpected_errors_are_not_converted(navigation):
    _, service = navigation
    error = RuntimeError("programming failure")
    service.overview.side_effect = error
    result = CliRunner().invoke(main, ["graph", "overview"])
    assert result.exit_code == 1
    assert result.exception is error
    assert result.stdout == result.stderr == ""
