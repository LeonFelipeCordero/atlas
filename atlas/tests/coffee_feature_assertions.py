"""Source-reviewed feature contracts are deliberately not updated with snapshots."""

import json


def assert_project_sources(bundle, expected):
    files = bundle["extraction"]["files"]
    assert {file["source"]["path"] for file in files} == expected
    assert set(bundle["extraction"]["structures"]) == expected
    assert {node["path"] for node in bundle["graph"]["nodes"] if node["level"] == "file"} == expected
    report = bundle["cli"]["report-json"]["output"]
    assert {node["path"] for node in report["nodes"] if node["level"] == "file"} == expected


def declaration_contract(symbol):
    return {field: symbol[field] for field in (
        "signature", "kind", "decorators", "parameter_count", "complexity",
    )}


def ordered_contracts(records):
    return sorted(records, key=lambda record: json.dumps(record, sort_keys=True))


def relationship_contract(edge, target):
    return {
        "type": edge["type"], "confidence": edge["confidence"],
        "evidence": edge["evidence"], "typeOnly": edge.get("type_only", edge.get("typeOnly", False)),
        "target": target["qualifiedName"], "targetKind": target["kind"],
        "targetSignature": target.get("signature"),
    }


def feature_relationships(bundle, keys):
    nodes = {node["stableKey"]: node for node in bundle["graph"]["nodes"]}
    edges = bundle["analysis"]["resolved"]["connections"]
    return ordered_contracts([
        relationship_contract(edge, nodes[edge["target_key"]])
        for edge in edges if edge["source_key"] in keys
    ])


def graph_relationships(bundle, keys):
    nodes = {node["stableKey"]: node for node in bundle["graph"]["nodes"]}
    return ordered_contracts([
        relationship_contract(edge, nodes[edge["targetStableKey"]])
        for edge in bundle["graph"]["edges"]
        if edge["sourceStableKey"] in keys and edge["type"] != "CONTAINS"
    ])


def assert_feature_contract(matches, bundle, feature):
    keys = {symbol["key"] for symbol in matches}
    enriched = [symbol for symbol in bundle["analysis"]["symbols"] if symbol["key"] in keys]
    assert len(enriched) == len(matches), feature
    assert ordered_contracts([declaration_contract(symbol) for symbol in enriched]) == feature["declarations"], feature
    assert feature_relationships(bundle, keys) == feature["relationships"], feature
    assert graph_relationships(bundle, keys) == feature["relationships"], feature
    for symbol in enriched:
        assert_graph_and_cli_metrics(symbol, bundle)


def assert_graph_and_cli_metrics(symbol, bundle):
    graph = {node["stableKey"]: node for node in bundle["graph"]["nodes"]}
    assert symbol["key"] in graph, symbol
    if symbol["complexity"] is None:
        return
    properties = graph[symbol["key"]]["properties"]
    assert properties.get("parameterCount") == symbol["parameter_count"]
    assert properties["cyclomaticComplexity"] == symbol["complexity"]["cyclomaticComplexity"]
    assert_cli_metrics(symbol, bundle["cli"]["report-json"]["output"])


def assert_cli_metrics(symbol, report):
    nodes = {node["stableKey"]: node for node in report["nodes"]}
    metrics = nodes[symbol["key"]]["metrics"]
    assert metrics.get("parameterCount") == symbol["parameter_count"]
    assert metrics["weightedComplexity"] == symbol["complexity"]["cyclomaticComplexity"]
    assert metrics["lineCount"] == symbol["line_count"]
