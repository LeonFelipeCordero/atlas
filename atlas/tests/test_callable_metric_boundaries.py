"""Independent unknown-count, receiver, and end-exclusive metric contracts."""

from dataclasses import replace
from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from atlas.domain.models import SourceFile
from atlas.indexer import analyze_repository
from atlas.metrics.adapters import get_metric_adapter
from atlas.metrics.callables import callable_metrics
from atlas.parsing.parser import parse_file
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_parsed, coffee_source, coffee_symbols

VARIANTS = Path(__file__).parent / "fixtures/variants/metrics"
TRACKING = "src/coffee/orders/tracking.py"


@pytest.mark.parametrize(("filename", "language", "node_type"), [
    ("tracking_malformed.py", "python", "function_definition"),
    ("tracking_mixed_arity.ex", "elixir", "anonymous_function"),
])
def test_malformed_header_and_mixed_clause_arity_are_unknown(filename, language, node_type):
    content = (VARIANTS / filename).read_bytes()
    root = get_parser(language).parse(content).root_node
    declaration, = [node for node in walk(root) if node.type == node_type]
    if language == "python":
        assert declaration.has_error
    else:
        assert not root.has_error  # Valid grammar, but inconsistent clause inputs.
    assert get_metric_adapter(language).parameter_count(declaration) is None
    source = SourceFile(filename, VARIANTS / filename, language, content)
    file = parse_file(source)
    callable_metrics(file)
    symbol, = [symbol for symbol in file.symbols if symbol.kind in {"function", "method"}]
    assert symbol.parameter_count is None
    assert symbol.line_count == 1


@pytest.mark.parametrize(("filename", "expected"), [
    ("tracking_empty.py", 0),
    ("tracking_newline.py", 1),
    ("tracking_comment.py", 1),
    ("tracking_comment_lf.py", 1),
    ("tracking_comment_blank.py", 2),
    ("tracking_comment_crlf.py", 2),
])
def test_named_layout_variants_count_physical_lines(tmp_path, filename, expected):
    content = (VARIANTS / filename).read_bytes()
    (tmp_path / filename).write_bytes(content)
    graph = analyze_repository(tmp_path)
    file, = [node for node in graph.nodes if node["type"] == "file"]
    assert file["properties"]["lineCount"] == expected
    assert not any(node["type"] in {"function", "method"} for node in graph.nodes)


@pytest.mark.parametrize("case", [
    # A method's first ordinary input is its receiver, regardless of its spelling.
    ('queue: "PickupQueue", courier:', 'counter: "PickupQueue", courier:', "PickupQueue.dispatch", 2),
    ('cls, orders: list[Order]', 'counter_type, orders: list[Order]', "PickupQueue.from_orders", 1),
    # Defaults and typed defaults still denote receivers.
    ('queue: "PickupQueue", courier:', 'queue: "PickupQueue" = None, courier:', "PickupQueue.dispatch", 2),
    ('self: "PickupQueue", order: Order', 'self=None, order: Order = None', "PickupQueue.record", 1),
    # A first star input is NOT an implicit receiver, even when named self.
    ('self, *customers: str', '*self: str', "PickupQueue.collect", 1),
    ('self, **metadata: str', '**self: str', "PickupQueue.annotate", 1),
    # Comment trivia on a static decorator cannot turn it into an instance method.
    ('@staticmethod', '@staticmethod # Counter notification does not consume a receiver.', "PickupQueue.notification", 2),
    # Receiver-looking names outside class method position remain declared inputs.
    ('order: Order, channel: str) -> str:', 'self: Order, cls: str) -> str:', "tracking_label", 2),
    ('def label(order: Order, channel: str):', 'def label(self: Order, cls: str):', "PickupQueue.record.label", 2),
])
def test_python_receiver_discriminators_on_whole_tracking_source(case):
    old, new, name, expected = case
    source = coffee_source("python", TRACKING)
    assert source.source.count(old.encode()) == 1
    mutation = replace(source, source=source.source.replace(old.encode(), new.encode()))
    assert not get_parser("python").parse(mutation.source).root_node.has_error
    file = parse_file(mutation)
    assert file.parse_error is None
    callable_metrics(file)
    symbol, = coffee_symbols(file, name)
    assert symbol.parameter_count == expected
    assert source.source == coffee_source("python", TRACKING).source


@pytest.mark.parametrize(("end_column", "expected"), [(1, 5), (2, 6)])
def test_native_end_exclusive_column_zero_on_real_nested_tracking_spans(end_column, expected):
    file = coffee_parsed("python", TRACKING)
    record, = coffee_symbols(file, "PickupQueue.record")
    nested, = coffee_symbols(file, "PickupQueue.record.label")
    before = repr(file)
    # Model a native span ending at the next row's column zero (one-based column 1).
    synthetic = replace(record, end_byte=record.end_byte + 1,
                        end_line=record.end_line + 1, end_column=end_column,
                        line_count=None, parameter_count=None)
    local = replace(nested, line_count=None, parameter_count=None)
    retained = replace(file, symbols=[synthetic, local])
    callable_metrics(retained)
    assert synthetic.line_count == expected
    assert (local.line_count, local.parameter_count) == (2, 2)
    assert local.parent_key == synthetic.key
    assert repr(file) == before
