"""Parsing extracts spans; explicit source-backed metrics enrich those records."""

from tests.source_snapshot_fixture import case_bytes

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity, SourceFile
from atlas.metrics.callables import add_callable_metrics, callable_metrics
from atlas.parsing.parser import parse_file, parse_files


@pytest.mark.parametrize('case_id', [
    'metric_phases-callable_metrics_are_explicit_and_use_decoded_byte_spans-python',
    'metric_phases-callable_metrics_are_explicit_and_use_decoded_byte_spans-python-2',
], ids=['valid-prefix', 'invalid-utf8-prefix'])
@pytest.mark.parametrize("phase", ["file", "repository"])
def test_callable_metrics_are_explicit_and_use_decoded_byte_spans(case_id, phase):
    body = case_bytes('metrics', 'metric_phases-callable_metrics_are_explicit_and_use_decoded_byte_spans-python-4', 'sample.py')
    content = case_bytes('metrics', case_id, 'sample.py')
    prefix = content[:len(content) - len(body)]
    source = SourceFile("sample.py", Path("/sample.py"), "python", content)
    repository = parse_files([source]) if phase == "repository" else None
    file = repository.files[0] if repository is not None else parse_file(source)
    assert file.parse_error is None
    assert len(file.symbols) == 1
    symbol = file.symbols[0]
    assert symbol.complexity is symbol.line_count is symbol.parameter_count is None
    decoded = source.source.decode("utf-8", errors="replace").encode("utf-8")
    assert symbol.start_byte == len(prefix.decode("utf-8", errors="replace").encode("utf-8"))
    assert decoded[symbol.start_byte:symbol.end_byte] == body.rstrip(b"\n")
    identity = (symbol.key, symbol.start_byte, symbol.end_byte, symbol.signature)
    parser = Mock(wraps=get_parser("python"))
    with patch("atlas.metrics.callables.get_parser", return_value=parser) as factory:
        if repository is not None:
            add_callable_metrics(repository)
        else:
            callable_metrics(file)
    factory.assert_called_once_with("python")
    parser.parse.assert_called_once_with(decoded)
    assert file.symbols[0] is symbol
    assert (symbol.key, symbol.start_byte, symbol.end_byte, symbol.signature) == identity
    assert symbol.parameter_count == 2
    assert symbol.line_count == 4
    assert symbol.complexity == Complexity(2, 0, 0, 2, 1)


def test_metric_enrichment_does_not_parse_files_without_callables():
    source = SourceFile("sample.py", Path("/sample.py"), "python", case_bytes('metrics', 'metric_phases-metric_enrichment_does_not_parse_files_without_callables-python', 'sample.py'))
    repository = parse_files([source])
    with patch("atlas.metrics.callables.get_parser") as parser:
        add_callable_metrics(repository)
    parser.assert_not_called()
