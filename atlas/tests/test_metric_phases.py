"""Parsing extracts spans; explicit metrics enrich complete coffee source records."""

from dataclasses import asdict, replace
from unittest.mock import Mock, patch

import pytest
from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.callables import add_callable_metrics, callable_metrics
from atlas.parsing.parser import parse_file, parse_files
from tests.coffee_consolidation import coffee_source, coffee_symbols
from tests.metric_test_support import assert_symbol_identity, restore_file_metrics


def assert_decoded_span(file, baseline, prefix):
    symbol = coffee_symbols(file, "Fulfillment.reserve")[0]
    original_symbol = coffee_symbols(baseline, "Fulfillment.reserve")[0]
    decoded = file.source.source.decode("utf-8", errors="replace").encode("utf-8")
    offset = len(prefix.decode("utf-8", errors="replace").encode("utf-8"))
    assert symbol.start_byte == original_symbol.start_byte + offset
    assert symbol.end_byte == original_symbol.end_byte + offset
    assert decoded[symbol.start_byte:symbol.end_byte] == baseline.source.source[
        original_symbol.start_byte:original_symbol.end_byte
    ]
    return decoded


def enrich_once(file, repository, decoded):
    parser = Mock(wraps=get_parser("python"))
    with patch("atlas.metrics.callables.get_parser", return_value=parser) as factory:
        if repository is not None:
            add_callable_metrics(repository)
        else:
            callable_metrics(file)
    factory.assert_called_once_with("python")
    parser.parse.assert_called_once_with(decoded)


@pytest.mark.parametrize("prefix", [b"# caf\xc3\xa9 pickup\n", b"# caf\xe9 pickup\n"],
                         ids=["valid-prefix", "invalid-utf8-prefix"])
@pytest.mark.parametrize("phase", ["file", "repository"])
def test_callable_metrics_are_explicit_and_use_decoded_byte_spans(prefix, phase):
    original = coffee_source("python", "src/coffee/orders/fulfillment.py")
    baseline = parse_file(original)
    source = replace(original, source=prefix + original.source)
    repository = parse_files([source]) if phase == "repository" else None
    file = repository.files[0] if repository is not None else parse_file(source)
    assert file.parse_error is None
    symbols = list(file.symbols)
    before = asdict(file)
    assert all(s.complexity is s.line_count is s.parameter_count is None for s in symbols)
    symbol = coffee_symbols(file, "Fulfillment.reserve")[0]
    decoded = assert_decoded_span(file, baseline, prefix)
    enrich_once(file, repository, decoded)
    assert_symbol_identity(file.symbols, symbols)
    after = asdict(file)
    restore_file_metrics(after, before)
    assert after == before  # Includes native signatures, record order, calls and imports.
    assert symbol.parameter_count == 2
    assert symbol.line_count == 4
    assert symbol.complexity == Complexity(2, 0, 0, 2, 1)


def test_metric_enrichment_does_not_parse_files_without_callables():
    repository = parse_files([coffee_source("rust", "brewing/mod.rs")])
    assert repository.files[0].parse_error is None
    assert not any(s.kind in {"function", "method"} for s in repository.symbols)
    before = asdict(repository)
    with patch("atlas.metrics.callables.get_parser") as parser:
        add_callable_metrics(repository)
    parser.assert_not_called()
    assert asdict(repository) == before
