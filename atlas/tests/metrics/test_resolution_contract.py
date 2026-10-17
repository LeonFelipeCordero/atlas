"""Resolution requests retain lexical context and immutable syntax metadata."""

from dataclasses import FrozenInstanceError, replace

import pytest

from atlas.metrics.resolution_contract import (
    FUNCTIONS, SCOPES, CallTarget, DeclarationLookup, ImportRequest, ResolutionRequest,
)
from tests.metrics.resolution_support import call, node, parsed_file, symbol


def test_import_request_defaults_and_context_override():
    file = parsed_file()
    request = ImportRequest(file, "package")

    located = replace(request, position=0, source="import package")

    assert (request.file, request.path, request.position, request.source) == (file, "package", None, "")
    assert located == ImportRequest(file, "package", 0, "import package")


def test_resolution_request_replace_keeps_call_and_owner():
    file, site, owner = parsed_file(), call(), symbol()
    request = ResolutionRequest(file, site, owner, "run")

    qualified = replace(request, name="other", qualifier="receiver")

    assert qualified == ResolutionRequest(file, site, owner, "other", "receiver")
    assert request.qualifier is None


@pytest.mark.parametrize("record", [
    ImportRequest(parsed_file(), "pkg"),
    ResolutionRequest(parsed_file(), call(), None, "run"),
    CallTarget(None, None, "run", None),
    DeclarationLookup("run", node(), 0),
])
def test_records_reject_field_assignment(record):
    with pytest.raises(FrozenInstanceError):
        record.name = "changed"


def test_syntax_records_preserve_node_identity_and_zero_position():
    callee, receiver = node(value="run"), node(value="service")

    target = CallTarget(callee, receiver, "run", "service")
    lookup = DeclarationLookup("run", callee, 0)

    assert (target.callee is callee, target.receiver is receiver, target.name, target.qualifier) == (
        True, True, "run", "service")
    assert (lookup.name, lookup.node is callee, lookup.position) == ("run", True, 0)


def test_scopes_include_all_functions_and_non_callable_blocks():
    assert FUNCTIONS <= SCOPES
    assert {"lambda", "closure_expression", "constructor_declaration", "func_literal"} <= FUNCTIONS
    assert {"class_definition", "block", "compound_statement"} <= SCOPES - FUNCTIONS
    assert "identifier" not in SCOPES
