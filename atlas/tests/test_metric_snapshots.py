"""Lossless callable records and strict thresholds on whole coffee applications."""

from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import PurePosixPath

import pytest

from atlas.domain.models import Complexity, ParsedRepository, Symbol
from atlas.metrics.adapters import get_metric_adapter
from atlas.metrics.adapters.base import COMMON_METRICS
from atlas.metrics.artifact import _ArtifactContents, _add_file_nodes
from atlas.metrics.callables import add_callable_metrics
from atlas.metrics.check import _MetricLimit, _metric_finding, _node_findings
from atlas.metrics.complexity import calculate_complexity
from atlas.metrics.config import CheckConfig
from atlas.parsing.parser import parse_files
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_consolidation import coffee_node, coffee_parsed, coffee_source, coffee_symbols
from tests.coffee_fixture import LANGUAGES, coffee_sources
from tests.metric_test_support import assert_symbol_identity, restore_repository_metrics

METRIC_RULES = {
    "lineCount": ("maxFunctionLines", "Lines"),
    "parameterCount": ("maxParameters", "Parameters"),
    "weightedComplexity": ("maxWeightedComplexity", "Weighted complexity"),
    "maxDecisionDepth": ("maxDecisionDepth", "Decision depth"),
    "nestedLoops": ("maxNestedLoops", "Nested loops"),
}
DISABLED = CheckConfig(**{rule: None for rule in CheckConfig.model_fields})


def metric_subject(path, line, subject):
    return {"path": path, "line": line, "subject": subject,
            "kind": "function", "level": "symbol"}


def assert_thresholds(metrics, subject):
    node = {"metrics": metrics, **subject}
    before = deepcopy(node)
    assert _node_findings(node, DISABLED) == []
    rules = {"lineCount": ("maxFileLines", "Lines")} if node["kind"] == "file" else METRIC_RULES
    defaults = CheckConfig()
    default_findings = [
        expected_finding(node, _MetricLimit(rule, metric, getattr(defaults, rule)), label)
        for metric, (rule, label) in rules.items()
        if metrics.get(metric) is None or metrics[metric] > getattr(defaults, rule)
    ]
    for metric in metrics:
        rule, label = rules[metric]
        assert_metric_threshold(node, _MetricLimit(rule, metric, 0), label)
    assert _node_findings(node, CheckConfig()) == default_findings
    assert node == before


def assert_metric_threshold(node, limit, label):
    actual = node["metrics"][limit.metric]
    if actual is not None:
        assert _metric_finding(node, replace(limit, maximum=actual)) is None
    failing = replace(limit, maximum=0 if actual is None else actual - 1)
    assert _metric_finding(node, failing) == expected_finding(node, failing, label)


def expected_finding(node, limit, label):
    actual = node["metrics"].get(limit.metric)
    details = (f"{label} is unavailable; cannot evaluate maximum {limit.maximum}." if actual is None
               else f"{label} is {actual} (maximum: {limit.maximum}).")
    return {"rule": limit.rule, "metric": limit.metric, "subject": node["subject"],
            "files": [{"path": node["path"], "line": node["line"]}],
            "actual": actual, "limit": limit.maximum, "details": [details]}


@pytest.mark.parametrize("language", LANGUAGES)
def test_callable_records(language):
    sources = coffee_sources(language)
    repository = parse_files(sources)
    before = asdict(repository)
    symbols = list(repository.symbols)
    assert [file.source for file in repository.files] == sources
    assert all(file.parse_error is None for file in repository.files)
    assert all(s.complexity is s.line_count is s.parameter_count is None for s in symbols)
    add_callable_metrics(repository)
    assert_symbol_identity(repository.symbols, symbols)
    after = asdict(repository)
    restore_repository_metrics(after, before)
    assert after == before  # No normalization/deduplication of native records.
    enriched = asdict(repository)
    add_callable_metrics(repository)
    assert asdict(repository) == enriched
    for file in repository.files:
        assert_file_record(file)
        assert_file_callables(file)


def assert_file_callables(file):
    for symbol in file.symbols:
        assert_callable_record(symbol)


def assert_callable_record(symbol):
    if symbol.kind not in {"function", "method"}:
        assert symbol.complexity is symbol.line_count is symbol.parameter_count is None
        return
    assert isinstance(symbol.complexity, Complexity)
    assert symbol.line_count == symbol.end_line - symbol.start_line + int(symbol.end_column > 1)
    assert symbol.parameter_count is None or type(symbol.parameter_count) is int
    metrics = {"lineCount": symbol.line_count, "parameterCount": symbol.parameter_count,
               "weightedComplexity": symbol.complexity.cyclomaticComplexity,
               "maxDecisionDepth": symbol.complexity.maxDecisionDepth,
               "nestedLoops": symbol.complexity.loopNestedComplexity}
    subject = metric_subject(symbol.file_path, symbol.start_line, symbol.key)
    assert_thresholds(metrics, subject | {"kind": symbol.kind})


def assert_file_record(file):
    contents = _ArtifactContents([], [], [])
    _add_file_nodes(ParsedRepository([file]), contents)
    source = file.source
    parent = f"module:{PurePosixPath(source.path).parent.as_posix()}"
    line_count = len(source.source.splitlines())
    assert file.content_hash == sha256(source.source).hexdigest()
    assert contents.nodes == [{
        "stableKey": f"file:{source.path}", "type": "file", "kind": "file", "level": "file",
        "language": source.language, "name": source.absolute_path.name,
        "qualifiedName": source.path, "path": source.path, "parentStableKey": parent,
        "properties": {"bytes": len(source.source), "lineCount": line_count,
                       "sha256": file.content_hash},
    }]
    assert contents.edges == [{
        "sourceStableKey": parent, "targetStableKey": f"file:{source.path}", "type": "CONTAINS",
        "confidence": "EXTRACTED", "path": source.path, "line": 1, "evidence": None,
    }]
    assert contents.diagnostics == []
    subject = metric_subject(source.path, 1, source.path)
    assert_thresholds({"lineCount": line_count}, subject | {"kind": "file"})


@pytest.mark.parametrize("sample", [
    ("python", "src/coffee/brewing/brewer.py", "Brewer.score", Complexity(5, 1, 1, 7, 3)),
    ("kotlin", "brewing/Brewer.kt", "Brewer.score", Complexity(5, 1, 1, 7, 3)),
    ("rust", "brewing/brewer.rs", "score", Complexity(5, 1, 1, 7, 3)),
    ("java", "brewing/Brewer.java", "Brewer.score", Complexity(5, 1, 1, 7, 3)),
    ("go", "brewing/brewer.go", "score", Complexity(5, 1, 1, 7, 3)),
    ("javascript", "brewing/Brewer.js", "Brewer.score", Complexity(5, 1, 1, 7, 3)),
    ("typescript", "brewing/Brewer.ts", "Brewer.score", Complexity(5, 1, 1, 7, 3)),
    ("tsx", "Basket.tsx", "Basket.add", Complexity(2, 0, 0, 2, 1)),
    ("elixir", "brewing/recipe.ex", "Coffee.Brewing.Recipe.portions", Complexity(3, 0, 0, 3, 1)),
])
def test_grammar_complexity(sample):
    language, path, name, expected = sample
    node = coffee_node(language, path, name)
    before = (node.type, node.start_byte, node.end_byte, node.text)
    assert calculate_complexity(node) == expected
    assert calculate_complexity(node, get_metric_adapter(language).metrics) == expected
    assert (node.type, node.start_byte, node.end_byte, node.text) == before
    assert_thresholds({"weightedComplexity": expected.cyclomaticComplexity,
                       "maxDecisionDepth": expected.maxDecisionDepth,
                       "nestedLoops": expected.loopNestedComplexity},
                      metric_subject(path, node.start_point.row + 1, name))


def test_explicit_empty_policy_keeps_whole_source_scopes_excluded():
    source = coffee_source("python", "src/coffee/brewing/brewer.py")
    root = ParsedSyntax(source).tree()
    assert not root.has_error
    assert calculate_complexity(root) == Complexity(2, 0, 0, 2, 1)
    assert calculate_complexity(root, replace(COMMON_METRICS, decisions=frozenset())) == Complexity(1, 0, 0, 1, 0)


def test_native_overload_records_keep_signatures_spans_and_order():
    file = coffee_parsed("typescript", "ordering/Orders.ts")
    assert [s.name for s in file.symbols] == [
        "priceOrder", "lineTotal", "<anonymous>", "<anonymous>", "createOrder", "drinkTickets",
        "ticket", "pickupQueue", "quote", "quote", "quote", "quoteWithFees", "groupTickets",
        "<anonymous>", "<anonymous>",
    ]
    records = coffee_symbols(file, "quote")
    expected = [
        (1236, 1273, 31, 31, 45, "function quote(order: Order): number;", 1, 1, Complexity(1, 0, 0, 1, 0)),
        (1281, 1336, 32, 32, 63, "function quote(name: string, quantity: number): number;", 1, 2, Complexity(1, 0, 0, 1, 0)),
        (1344, 1528, 33, 37, 2, "function quote(orderOrName: Order | string, quantity = 1): number", 5, 2, Complexity(2, 0, 0, 2, 1)),
    ]
    assert records == [Symbol(
        key=f"symbol:ordering/Orders.ts::quote:{start}", file_path="ordering/Orders.ts",
        language="typescript", name="quote", qualified_name="ordering/Orders.ts::quote",
        kind="function", parent_key="file:ordering/Orders.ts", start_byte=start, end_byte=end,
        start_line=line, start_column=8, end_line=end_line, end_column=column,
        signature=signature, visibility=None, decorators=[], complexity=complexity,
        line_count=lines, parameter_count=parameters,
    ) for start, end, line, end_line, column, signature, lines, parameters, complexity in expected]


def test_native_elixir_clauses_remain_separate_records():
    file = coffee_parsed("elixir", "brewing/brewer.ex")
    assert [s.name for s in file.symbols] == [
        "Coffee.Brewing.Brewer", "brew", "brew", "<anonymous>", "serve", "<anonymous>",
        "retry", "retry", "score", "<anonymous>", "<anonymous>", "classify", "ready", "calibrate", "main",
    ]
    records = coffee_symbols(file, "Coffee.Brewing.Brewer.retry")
    expected = [
        (762, 807, 26, 48, "def retry(attempts) when attempts <= 0, do:", Complexity(2, 0, 0, 2, 1)),
        (810, 858, 27, 51, "def retry(attempts), do:", Complexity(1, 0, 0, 1, 0)),
    ]
    assert records == [Symbol(
        key=f"symbol:brewing/brewer.ex::Coffee.Brewing.Brewer.retry:{start}",
        file_path="brewing/brewer.ex", language="elixir", name="retry",
        qualified_name="brewing/brewer.ex::Coffee.Brewing.Brewer.retry", kind="function",
        parent_key="symbol:brewing/brewer.ex::Coffee.Brewing.Brewer:0",
        start_byte=start, end_byte=end, start_line=line, start_column=3,
        end_line=line, end_column=column, signature=signature, visibility="public", decorators=[],
        complexity=complexity, line_count=1, parameter_count=1,
    ) for start, end, line, column, signature, complexity in expected]


def test_implicit_kotlin_lambda_parameter_is_unavailable_not_zero():
    file = coffee_parsed("kotlin", "brewing/Brewer.kt")
    callback = coffee_symbols(file, "Brewer.brew.<anonymous>")[0]
    assert callback.parameter_count is None
    assert callback.complexity == Complexity(1, 0, 0, 1, 0)
    assert_thresholds({"parameterCount": None},
                      metric_subject(callback.file_path, callback.start_line, callback.key))
