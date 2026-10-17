"""Manifest values and orchestration without parser or filesystem integration."""

import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from atlas.domain.mutation_candidates import MutationCandidate, MutationSpan
from atlas.mutations import manifests as module
from atlas.mutations.rules import MutationRule, RuleMapping


@pytest.fixture
def candidate():
    def make(**overrides):
        span = MutationSpan(startByte=3, endByte=4, startLine=1, endLine=1, startColumn=4, endColumn=5)
        return MutationCandidate.model_validate({
            "id": "add", "sourceHash": "source-hash", "language": "python", "path": "café.py",
            "kind": "arithmetic", "operator": "+", "originalText": "+", "span": span,
            "expressionSpan": span.model_copy(update={"startByte": 0, "endByte": 6}),
            "expressionText": "é + b", **overrides,
        })
    return make


def rule(**overrides):
    return MutationRule.model_validate({
        "id": "arithmetic.add-to-subtract", "kind": "arithmetic", "version": 1,
        "mappings": (RuleMapping(language="python", original="+", replacement="-"),), **overrides,
    })


def test_manifest_has_canonical_identity_and_utf8_bytes(candidate):
    site = candidate(originalText="é")

    result = module._manifest(site, rule(version=7), "≤")

    expected = {
        "candidateId": "add", "sourceHash": "source-hash", "ruleId": "arithmetic.add-to-subtract",
        "ruleVersion": 7, "language": "python", "path": "café.py", "span": site.span.model_dump(),
        "originalText": "é", "originalBytes": "w6k=", "replacement": "≤", "replacementBytes": "4omk",
    }
    canonical = json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert result.model_dump() == {"id": hashlib.sha256(canonical.encode()).hexdigest(), **expected}
    assert base64.b64decode(result.replacementBytes) == "≤".encode()
    assert module._manifest(site, rule(version=7), "≤") == result


@pytest.mark.parametrize("change", [
    {"id": "another"}, {"sourceHash": "other"}, {"path": "other.py"},
    {"language": "javascript"}, {"originalText": "-"},
])
def test_manifest_identity_changes_with_source_metadata(candidate, change):
    assert module._manifest(candidate(**change), rule(), "-").id != module._manifest(candidate(), rule(), "-").id


def test_manifest_identity_changes_with_rule_version_and_replacement(candidate):
    baseline = module._manifest(candidate(), rule(), "-")
    assert module._manifest(candidate(), rule(version=2), "-").id != baseline.id
    assert module._manifest(candidate(), rule(), "*").id != baseline.id
    different_rule = module._manifest(candidate(), rule(id="another-rule"), "-")
    assert different_rule.ruleId == "another-rule"
    assert different_rule.id != baseline.id


def test_rule_edits_filter_language_operator_and_noop(candidate):
    mappings = tuple(RuleMapping(language=language, original=original, replacement=replacement)
                     for language, original, replacement in [
                         ("javascript", "+", "js"), ("python", "-", "wrong"),
                         ("python", "+", "+"), ("python", "+", "-"), ("python", "+", "*"),
                     ])

    result = module._rule_edits(candidate(), rule(mappings=mappings))

    assert result == [module._manifest(candidate(), rule(mappings=mappings), token) for token in ("-", "*")]


@pytest.mark.parametrize("case", [
    ("arithmetic", ["arithmetic.add-to-subtract"], {(0, 6)}, ["-"]),
    ("arithmetic", [], {(0, 6)}, []),
    ("arithmetic", ["arithmetic.add-to-subtract"], {(0, 7)}, []),
    ("arithmetic", ["arithmetic.add-to-subtract"], {(1, 6)}, []),
    ("comparison", ["arithmetic.add-to-subtract"], {(0, 6)}, []),
    ("comparison", ["comparison.less-to-greater"], set(), [">"]),
    ("condition", ["arithmetic.add-to-subtract"], {(0, 6)}, []),
])
def test_edits_require_selected_kind_and_binary_expression(candidate, case):
    kind, selected, spans, expected = case
    site = candidate(kind=kind, operator="<" if kind == "comparison" else "+",
                     originalText="<" if kind == "comparison" else "+")
    assert [item.replacement for item in module._edits(site, selected, spans)] == expected


def test_verified_edits_sort_inputs_and_cache_by_path_and_language(candidate, monkeypatch):
    sites = [candidate(path="z.py", id="z"), candidate(id="b"),
             candidate(id="z", language="javascript"), candidate(id="a")]
    inventory = Mock(side_effect=lambda root, site: (site.path, site.language))
    edits = Mock(side_effect=lambda site, verified, rules: [site.id + ":" + site.language])
    monkeypatch.setattr(module, "_source_inventory", inventory)
    monkeypatch.setattr(module, "_candidate_edits", edits)
    selected = ["arithmetic.add-to-subtract"]

    result = list(module._verified_edits(Path("/repo"), sites, selected))

    assert result == ["z:javascript", "a:python", "b:python", "z:python"]
    assert [(args[0][1].path, args[0][1].language) for args in inventory.call_args_list] == [
        ("café.py", "javascript"), ("café.py", "python"), ("z.py", "python"),
    ]
    assert [args[0][1] for args in edits.call_args_list] == [
        ("café.py", "javascript"), ("café.py", "python"), ("café.py", "python"), ("z.py", "python"),
    ]
    assert all(args[0][2] is selected for args in edits.call_args_list)
    assert all(args[0][0] == Path("/repo") for args in inventory.call_args_list)


def test_generate_validates_rules_before_reading_sources(candidate, monkeypatch):
    verified = Mock()
    monkeypatch.setattr(module, "_verified_edits", verified)
    with pytest.raises(ValueError, match="Unknown mutation rule"):
        module.generate_manifests(Path("/repo"), [candidate()], ["unknown"])
    verified.assert_not_called()


def test_generate_deduplicates_exact_edits_but_keeps_distinct_source_edits(candidate, monkeypatch):
    first = module._manifest(candidate(), rule(), "-")
    duplicate = first.model_copy(update={"id": "duplicate", "candidateId": "overlap", "ruleId": "other-rule"})
    variants = [first.model_copy(update=change) for change in [
        {"path": "z.py"}, {"sourceHash": "new-hash"}, {"replacement": "*"},
        {"span": first.span.model_copy(update={"startByte": 2})},
        {"span": first.span.model_copy(update={"endByte": 5})},
    ]]
    monkeypatch.setattr(module, "_verified_edits", Mock(return_value=iter([first, duplicate, *variants])))

    result = module.generate_manifests(Path("/repo"), [], [])

    assert len(result) == 6
    assert duplicate not in result
    assert result == [variants[3], variants[2], first, variants[1], variants[4], variants[0]]


def test_generate_resolves_root_and_preserves_inputs(candidate, monkeypatch):
    sites, selected = [candidate()], ["arithmetic.add-to-subtract"]
    resolve = Mock(return_value=Path("/resolved"))
    verified = Mock(return_value=iter(()))
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(module, "_verified_edits", verified)

    assert module.generate_manifests(Path("relative"), sites, selected) == []
    verified.assert_called_once_with(Path("/resolved"), sites, selected)
    assert sites == [candidate()]
    assert selected == ["arithmetic.add-to-subtract"]


def test_generate_rejects_late_failure_instead_of_returning_partial_edits(candidate, monkeypatch):
    def verified(*args):
        yield module._manifest(candidate(), rule(), "-")
        raise ValueError("stale second source")
    monkeypatch.setattr(module, "_verified_edits", verified)

    with pytest.raises(ValueError, match="stale second source"):
        module.generate_manifests(Path("/repo"), [], [])


def test_verified_inventory_cache_is_local_to_each_request(candidate, monkeypatch):
    site = candidate()
    inventory = Mock(side_effect=["first-source", "changed-source", "other-repository"])
    monkeypatch.setattr(module, "_source_inventory", inventory)
    monkeypatch.setattr(module, "_candidate_edits", lambda site, verified, rules: [verified])

    first = list(module._verified_edits(Path("/repo"), [site, site], []))
    changed = list(module._verified_edits(Path("/repo"), [site], []))
    other_root = list(module._verified_edits(Path("/other"), [site], []))

    assert first == ["first-source", "first-source"]
    assert changed == ["changed-source"]
    assert other_root == ["other-repository"]
    assert inventory.call_count == 3


@pytest.mark.parametrize("dimension", ["ruleId", "replacement", "id"])
def test_generate_uses_all_output_sort_tiebreakers(candidate, monkeypatch, dimension):
    base = module._manifest(candidate(), rule(), "-")
    # Different hashes keep otherwise equal edits independent of deduplication.
    later = base.model_copy(update={dimension: "z", "sourceHash": "a"})
    earlier = base.model_copy(update={dimension: "a", "sourceHash": "z"})
    monkeypatch.setattr(module, "_verified_edits", Mock(return_value=iter([later, earlier])))

    assert module.generate_manifests(Path("/repo"), [], []) == [earlier, later]
