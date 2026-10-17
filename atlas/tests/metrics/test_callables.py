"""Callable enrichment uses retained bytes and adapter boundaries only."""

from unittest.mock import Mock

import pytest

from atlas.domain.models import Complexity, ParsedRepository
from atlas.metrics import callables
from tests.metrics.metric_core_support import parsed_file, symbol


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock]:
    parser = Mock()
    adapter = Mock()
    complexity = Mock(return_value=Complexity(2, 1, 0, 3, 3))
    monkeypatch.setattr(callables, "get_parser", Mock(return_value=parser))
    monkeypatch.setattr(callables, "get_metric_adapter", Mock(return_value=adapter))
    monkeypatch.setattr(callables, "calculate_complexity", complexity)
    adapter.parameter_count.return_value = 4
    return parser, adapter, complexity


@pytest.mark.parametrize(("kind", "end_line", "end_column", "expected_lines"), [
    ("function", 5, 1, 3), ("method", 5, 2, 4), ("function", 1, 1, 0),
])
def test_callable_span_bytes_and_adapter_metrics(boundaries, kind, end_line, end_column, expected_lines) -> None:
    parser, adapter, calculate = boundaries
    record = symbol(kind=kind, end_line=end_line, end_column=end_column)
    file = parsed_file(source=b"x\xffy", symbols=[record])
    node = parser.parse.return_value.root_node.descendant_for_byte_range.return_value

    result = callables.callable_metrics(file)

    assert result is None
    parser.parse.assert_called_once_with(b"x\xef\xbf\xbdy")
    parser.parse.return_value.root_node.descendant_for_byte_range.assert_called_once_with(2, 11)
    calculate.assert_called_once_with(node, adapter.metrics)
    adapter.parameter_count.assert_called_once_with(node)
    assert (record.line_count, record.parameter_count, record.complexity) == (
        expected_lines, 4, Complexity(2, 1, 0, 3, 3),
    )


def test_missing_syntax_node_only_sets_line_count(boundaries) -> None:
    parser, adapter, calculate = boundaries
    parser.parse.return_value.root_node.descendant_for_byte_range.return_value = None
    record = symbol(parameter_count=9, complexity=Complexity(1, 0, 0, 1, 0))

    callables.callable_metrics(parsed_file(symbols=[record]))

    assert (record.line_count, record.parameter_count, record.complexity) == (
        3, 9, Complexity(1, 0, 0, 1, 0),
    )
    calculate.assert_not_called()
    adapter.parameter_count.assert_not_called()


@pytest.mark.parametrize("kinds", [[], ["class", "constructor", "procedure"]])
def test_files_without_supported_callables_do_not_load_parser(monkeypatch, kinds) -> None:
    parser_loader = Mock(side_effect=AssertionError("parser must not load"))
    adapter_loader = Mock(side_effect=AssertionError("adapter must not load"))
    monkeypatch.setattr(callables, "get_parser", parser_loader)
    monkeypatch.setattr(callables, "get_metric_adapter", adapter_loader)
    records = [symbol(key=kind, kind=kind) for kind in kinds]

    callables.callable_metrics(parsed_file(symbols=records))

    assert [(s.line_count, s.parameter_count, s.complexity) for s in records] == [
        (None, None, None) for _ in kinds
    ]


def test_mixed_symbols_only_enriches_functions_and_methods(boundaries) -> None:
    records = [symbol(key=kind, kind=kind) for kind in ("class", "function", "method")]

    callables.callable_metrics(parsed_file(symbols=records))

    assert [(s.line_count, s.parameter_count) for s in records] == [(None, None), (3, 4), (3, 4)]


def test_repository_enrichment_visits_each_file_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    files = [parsed_file("a.py"), parsed_file("b.py")]
    enrich = Mock()
    monkeypatch.setattr(callables, "callable_metrics", enrich)

    result = callables.add_callable_metrics(ParsedRepository(files))

    assert result is None
    assert [call.args[0] for call in enrich.call_args_list] == files


def test_source_language_selects_parser_and_adapter(boundaries, monkeypatch) -> None:
    parser, adapter, _ = boundaries
    load_parser, load_adapter = Mock(return_value=parser), Mock(return_value=adapter)
    monkeypatch.setattr(callables, "get_parser", load_parser)
    monkeypatch.setattr(callables, "get_metric_adapter", load_adapter)
    file = parsed_file(symbols=[symbol(language="rust")])
    file.source.language = "rust"

    callables.callable_metrics(file)

    load_parser.assert_called_once_with("rust")
    load_adapter.assert_called_once_with("rust")


def test_parser_failures_are_not_silently_discarded(boundaries) -> None:
    parser, _, _ = boundaries
    parser.parse.side_effect = RuntimeError("parser unavailable")

    with pytest.raises(RuntimeError, match="parser unavailable"):
        callables.callable_metrics(parsed_file(symbols=[symbol()]))
