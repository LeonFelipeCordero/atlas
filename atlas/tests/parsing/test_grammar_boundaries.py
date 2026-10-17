"""Dependency failures and grammar capability decisions without native parsing."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from atlas.parsing import discovery, parser, structure


@pytest.mark.parametrize("language", ["python", "c", "unknown"])
def test_require_supported_language_accepts_only_supported_catalog_entries(language):
    if language == "python":
        assert discovery.require_supported_language(language) is None
    else:
        with pytest.raises(ValueError, match=f"Unsupported Python importer language: {language}"):
            discovery.require_supported_language(language)


@pytest.mark.parametrize("kinds, expected", [(["document", "call_expression"], True), (["document", "text"], False)])
def test_call_capability_uses_grammar_node_kinds(monkeypatch, kinds, expected):
    grammar = Mock(node_kind_count=len(kinds), node_kind_for_id=kinds.__getitem__)
    monkeypatch.setattr(parser, "get_language", lambda language: grammar)

    # Bypass the cache so this fake grammar cannot contaminate later tests.
    assert parser._has_call_nodes.__wrapped__("test") is expected


@pytest.mark.parametrize("case", [
    (None, "", None), ("tags", "", "tags"),
    (None, "adapter", "adapter"), ("tags", "adapter", "tagsadapter"),
])
def test_declaration_query_combines_native_and_adapter_queries(monkeypatch, case):
    native, supplemental, expected = case
    monkeypatch.setattr(structure, "get_tags_query", lambda language: native)
    monkeypatch.setattr(structure, "get_adapter", lambda language: SimpleNamespace(declaration_query=supplemental))
    monkeypatch.setattr(structure, "get_language", lambda language: "grammar")
    monkeypatch.setattr(structure, "Query", lambda grammar, query: (grammar, query))

    result = structure._declaration_query.__wrapped__("test")

    assert result == (None if expected is None else ("grammar", expected))


def test_query_compilation_failure_propagates(monkeypatch):
    failure = ValueError("invalid query")
    monkeypatch.setattr(structure, "get_tags_query", lambda language: "bad")
    monkeypatch.setattr(structure, "get_adapter", lambda language: SimpleNamespace(declaration_query=""))
    monkeypatch.setattr(structure, "get_language", lambda language: "grammar")
    monkeypatch.setattr(structure, "Query", Mock(side_effect=failure))

    with pytest.raises(ValueError) as caught:
        structure._declaration_query.__wrapped__("test")

    assert caught.value is failure
