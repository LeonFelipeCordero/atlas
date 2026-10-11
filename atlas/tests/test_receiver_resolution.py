"""Receiver fixtures use each grammar, not a shared source-text approximation."""

from tests.resolution_snapshot_support import fixture_sources
import pytest
from tests.test_semantic_resolution import repository, call_edges

CASES = ("java", "kotlin", "typescript", "tsx", "python", "go", "rust", "javascript")


@pytest.mark.parametrize("language", CASES)
def test_declared_receivers(language):
    repo = repository(
        language,
        fixture_sources(
            "receiver_resolution:test_declared_receivers:24-11", language=language
        ),
    )
    edges = [e for e in call_edges(repo) if e.evidence and ".persist()" in e.evidence]
    assert edges
    assert all(
        (
            e.target_key.startswith("symbol:") and "persist" in e.target_key
            for e in edges
        )
    ), edges


@pytest.mark.parametrize("language", CASES)
def test_unknown_receiver_never_uses_member_name(language):
    repo = repository(
        language,
        fixture_sources(
            "receiver_resolution:test_unknown_receiver_never_uses_member_name:34-11",
            language=language,
        ),
    )
    edges = call_edges(repo, "unknown.persist()")
    assert edges
    assert all((e.target_key.startswith("external:") for e in edges))


@pytest.mark.parametrize(
    "language, path, source",
    [
        ("python", "app.py", "reassigned-inferred-receiver-stays-external-python-01"),
        (
            "javascript",
            "app.js",
            "reassigned-inferred-receiver-stays-external-javascript-01",
        ),
        (
            "typescript",
            "app.ts",
            "reassigned-inferred-receiver-stays-external-javascript-01",
        ),
    ],
)
def test_reassigned_inferred_receiver_stays_external(language, path, source):
    edges = call_edges(
        repository(
            language,
            fixture_sources(
                "receiver_resolution:test_reassigned_inferred_receiver_stays_external:46-23",
                language=language,
            ),
        ),
        "local.persist()",
    )
    assert edges and all((e.target_key.startswith("external:") for e in edges))


def test_elixir_has_module_calls_not_instance_members():
    repo = repository(
        "elixir",
        fixture_sources(
            "receiver_resolution:test_elixir_has_module_calls_not_instance_members:51-11"
        ),
    )
    modules = call_edges(repo, "Service.persist()")
    dynamic = call_edges(repo, "service.persist()")
    assert modules and all((e.target_key.startswith("symbol:") for e in modules))
    assert dynamic and all((e.target_key.startswith("external:") for e in dynamic))
