"""Full callable records and strict threshold boundaries, independent of graph output."""

from dataclasses import replace

from tree_sitter_language_pack import get_parser

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters.base import COMMON_METRICS
from atlas.metrics.artifact import _ArtifactContents, _add_file_nodes
from atlas.metrics.callables import callable_metrics
from atlas.metrics.check import _MetricLimit, _metric_finding, _node_findings
from atlas.metrics.config import CheckConfig
from atlas.metrics.complexity import calculate_complexity
from atlas.parsing.parser import parse_file
from tests.parsing_snapshot_support import manifest, source_file
from tests.source_snapshot_fixture import assert_case_snapshot, case_bytes, snapshot_value


def thresholds(metrics, path, line, subject, kind='function'):
    node = {"metrics": metrics, "path": path, "line": line, "subject": subject,
            "kind": kind, "level": "symbol"}
    rules = {'lineCount': 'maxFunctionLines', 'parameterCount': 'maxParameters',
             'weightedComplexity': 'maxWeightedComplexity', 'maxDecisionDepth': 'maxDecisionDepth',
             'nestedLoops': 'maxNestedLoops'}
    if kind == 'file':
        rules['lineCount'] = 'maxFileLines'
    boundaries = {
        metric: {
            "at_limit": _metric_finding(node, _MetricLimit(rules[metric], metric, actual)),
            "below_limit": _metric_finding(node, _MetricLimit(rules[metric], metric, actual - 1)),
        } if actual is not None else {
            "unavailable": _metric_finding(node, _MetricLimit(rules[metric], metric, 0)),
        }
        for metric, actual in metrics.items()
    }
    disabled = _node_findings(node, CheckConfig(**{rule: None for rule in CheckConfig.model_fields}))
    assert disabled == []
    return {"disabled": disabled, "default_limits": _node_findings(node, CheckConfig()),
            "boundaries": boundaries}


def metric_value(case):
    source = source_file(case)
    file = parse_file(source)
    before = [(s.key, s.start_byte, s.end_byte, s.signature) for s in file.symbols]
    callable_metrics(file)
    assert before == [(s.key, s.start_byte, s.end_byte, s.signature) for s in file.symbols]
    return enriched_value(file)


def assert_metric_snapshot(file):
    case = next(case for case in manifest('metric_sources.json')
                if case['language'] == file.source.language and case['path'] == file.source.path
                and case_bytes(case['family'], case['case_id'], case['path']) == file.source.source)
    assert_case_snapshot('metrics', case['snapshot_id'], enriched_value(file))


def enriched_value(file):
    source = file.source
    findings = []
    for symbol in file.symbols:
        if symbol.kind not in {"function", "method"}:
            continue
        complexity = symbol.complexity
        metrics = {
            "lineCount": symbol.line_count, "parameterCount": symbol.parameter_count,
            "weightedComplexity": complexity.cyclomaticComplexity if complexity else None,
            "maxDecisionDepth": complexity.maxDecisionDepth if complexity else None,
            "nestedLoops": complexity.loopNestedComplexity if complexity else None,
        }
        findings.append(thresholds(metrics, source.path, symbol.start_line, symbol.key))
    contents = _ArtifactContents([], [], [])
    _add_file_nodes(ParsedRepository([file]), contents)
    file_record = contents.nodes[0]
    properties = file_record['properties']
    assert isinstance(properties, dict)
    file_metrics = {'lineCount': properties['lineCount']}
    return {"parse_error": file.parse_error, "records": file.symbols, "thresholds": findings,
            "file_record": file_record,
            "file_thresholds": thresholds(file_metrics, source.path, 1, source.path, 'file')}


def complexity_value(case):
    source = source_file(case)
    root = get_parser(source.language).parse(source.source).root_node
    stack = [root]
    target = None
    while stack:
        node = stack.pop()
        if [node.start_byte, node.end_byte] == case["span"] and node.type == case["node_type"]:
            target = node
            break
        stack.extend(reversed(node.named_children))
    assert target is not None, case["snapshot_id"]
    policy = replace(COMMON_METRICS, decisions=frozenset()) if case["policy"] == "empty" else None
    result = calculate_complexity(target, policy) if policy else calculate_complexity(target)
    metrics = {"weightedComplexity": result.cyclomaticComplexity,
               "maxDecisionDepth": result.maxDecisionDepth, "nestedLoops": result.loopNestedComplexity}
    return {"node_type": target.type, "span": case["span"], "source_bytes": target.text,
            "complexity": snapshot_value(result),
            "thresholds": thresholds(metrics, source.path, target.start_point.row + 1, target.type)}
