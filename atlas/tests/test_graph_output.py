"""CLI projection preserves graph identity and evidence without affecting input."""

from atlas.cli.graph_output import graph_output


def test_unresolved_projection_preserves_keys_and_evidence() -> None:
    key = "external:kotlin:callable:persist"
    payload = {
        "nodes": [{"stableKey": key, "type": "external", "level": "external",
                   "kind": "callable", "qualifiedName": key, "external": True}],
        "edges": [{"targetStableKey": key, "evidence": "orderService.persist(order)",
                   "confidence": "INFERRED", "type": "CALLS"}],
        "filters": {"key": key},
    }
    result = graph_output(payload)
    assert result["nodes"][0] == {
        "stableKey": key, "type": "unresolved", "level": "unresolved",
        "kind": "callable", "qualifiedName": "unresolved:kotlin:callable:persist",
        "external": False, "unresolved": True,
    }
    assert result["edges"] == payload["edges"]
    assert result["filters"] == payload["filters"]
    assert payload["nodes"][0]["type"] == "external"
