"""Negative receiver inference and existing identity-safety contracts."""

from tests.resolution_snapshot_support import fixture_sources
import pytest
from tests.test_semantic_resolution import repository, call_edges


def assert_target(language, sources, expected):
    evidence, internal = expected
    edges = call_edges(repository(language, sources), evidence)
    assert edges, evidence
    assert all(
        (e.target_key.startswith("symbol:" if internal else "external:") for e in edges)
    ), edges


@pytest.mark.parametrize(
    "case",
    [
        (
            "python",
            "app.py",
            "constructor-and-field-receivers-python-01",
            "self.service.persist()",
        ),
        (
            "python",
            "app.py",
            "constructor-and-field-receivers-python-02",
            "self.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "constructor-and-field-receivers-javascript-01",
            "this.service.persist()",
        ),
        (
            "javascript",
            "app.jsx",
            "constructor-and-field-receivers-javascript-02",
            "this.service.persist()",
        ),
        (
            "java",
            "App.java",
            "constructor-and-field-receivers-java-01",
            "local.persist()",
        ),
        (
            "java",
            "App.java",
            "constructor-and-field-receivers-java-02",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "constructor-and-field-receivers-python-03",
            "self.service.persist()",
        ),
        (
            "kotlin",
            "App.kt",
            "constructor-and-field-receivers-kotlin-01",
            "local.persist()",
        ),
        (
            "go",
            "app.go",
            "constructor-and-field-receivers-go-01",
            "a.service.persist()",
        ),
        (
            "rust",
            "app.rs",
            "constructor-and-field-receivers-rust-01",
            "self.service.persist()",
        ),
    ],
)
def test_constructor_and_field_receivers(case):
    language, path, source, evidence = case
    assert_target(
        language,
        fixture_sources(
            "receiver_safety:test_constructor_and_field_receivers:29-4", case=case
        ),
        (evidence, True),
    )


@pytest.mark.parametrize(
    "case",
    [
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-01",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-02",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-03",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-04",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-05",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-06",
            "self.service.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-07",
            "self.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unsafe-receivers-stay-external-javascript-01",
            "this.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unsafe-receivers-stay-external-javascript-02",
            "local.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unsafe-receivers-stay-external-javascript-03",
            "local.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unsafe-receivers-stay-external-javascript-04",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unsafe-receivers-stay-external-python-08",
            "local.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unsafe-receivers-stay-external-javascript-05",
            "local.persist()",
        ),
        (
            "typescript",
            "app.ts",
            "unsafe-receivers-stay-external-typescript-01",
            "local.persist()",
        ),
        (
            "java",
            "App.java",
            "unsafe-receivers-stay-external-java-01",
            "local.persist()",
        ),
        (
            "java",
            "App.java",
            "unsafe-receivers-stay-external-java-02",
            "local.persist()",
        ),
        (
            "java",
            "App.java",
            "unsafe-receivers-stay-external-java-03",
            "local.persist()",
        ),
        (
            "kotlin",
            "App.kt",
            "unsafe-receivers-stay-external-kotlin-01",
            "local.persist()",
        ),
        ("rust", "app.rs", "unsafe-receivers-stay-external-rust-01", "local.persist()"),
        ("go", "app.go", "unsafe-receivers-stay-external-go-01", "local.persist()"),
        ("go", "app.go", "unsafe-receivers-stay-external-go-02", "local.persist()"),
    ],
)
def test_unsafe_receivers_stay_external(case):
    language, path, source, evidence = case
    assert_target(
        language,
        fixture_sources(
            "receiver_safety:test_unsafe_receivers_stay_external:57-4", case=case
        ),
        (evidence, False),
    )


@pytest.mark.parametrize(
    "language, sources, evidence",
    [
        (
            "java",
            {
                "service/OrderService.java": "type-visibility-follows-import-and-namespace-context-java-01",
                "app/App.java": "type-visibility-follows-import-and-namespace-context-java-01",
            },
            "orderService.saveOrder(1)",
        ),
        (
            "kotlin",
            {
                "service/OrderService.kt": "type-visibility-follows-import-and-namespace-context-kotlin-01",
                "app/App.kt": "type-visibility-follows-import-and-namespace-context-kotlin-01",
            },
            "orderService.persist(1)",
        ),
        (
            "python",
            {
                "tools.py": "type-visibility-follows-import-and-namespace-context-python-01",
                "app.py": "type-visibility-follows-import-and-namespace-context-python-01",
            },
            "local.persist()",
        ),
        (
            "typescript",
            {
                "tools.ts": "type-visibility-follows-import-and-namespace-context-typescript-01",
                "app.ts": "type-visibility-follows-import-and-namespace-context-typescript-01",
            },
            "local.persist()",
        ),
        (
            "go",
            {
                "tools/tools.go": "type-visibility-follows-import-and-namespace-context-go-01",
                "app.go": "type-visibility-follows-import-and-namespace-context-go-01",
            },
            "local.persist()",
        ),
        (
            "rust",
            {
                "tools.rs": "type-visibility-follows-import-and-namespace-context-rust-01",
                "main.rs": "type-visibility-follows-import-and-namespace-context-rust-01",
            },
            "local.persist()",
        ),
    ],
)
def test_type_visibility_follows_import_and_namespace_context(
    language, sources, evidence
):
    assert_target(
        language,
        fixture_sources(
            "receiver_safety:test_type_visibility_follows_import_and_namespace_context:69-4",
            language=language,
        ),
        (evidence, True),
    )


@pytest.mark.parametrize(
    "language, sources",
    [
        (
            "python",
            {
                "tools.py": "type-visibility-follows-import-and-namespace-context-python-01",
                "app.py": "imported-receiver-member-rebinding-is-not-ignored-python-01",
            },
        ),
        (
            "javascript",
            {
                "tools.js": "type-visibility-follows-import-and-namespace-context-typescript-01",
                "app.js": "imported-receiver-member-rebinding-is-not-ignored-javascript-01",
            },
        ),
    ],
)
def test_imported_receiver_member_rebinding_is_not_ignored(language, sources):
    assert_target(
        language,
        fixture_sources(
            "receiver_safety:test_imported_receiver_member_rebinding_is_not_ignored:77-4",
            language=language,
        ),
        ("local.persist()", False),
    )


def test_exchange_broker_constructor_injected_websocket_client():
    assert_target(
        "java",
        fixture_sources(
            "receiver_safety:test_exchange_broker_constructor_injected_websocket_client:100-4"
        ),
        ("orderService.saveOrder(order)", True),
    )
    assert_target(
        "java",
        fixture_sources(
            "receiver_safety:test_exchange_broker_constructor_injected_websocket_client:101-4"
        ),
        ("orderCreatedWebSocketClient.sendAndWait(event)", True),
    )


def test_unrelated_constructor_assignments_are_separate_scopes():
    assert_target(
        "python",
        fixture_sources(
            "receiver_safety:test_unrelated_constructor_assignments_are_separate_scopes:106-4"
        ),
        ("self.service.persist()", True),
    )


def test_unimported_type_is_not_guessed_globally():
    assert_target(
        "python",
        fixture_sources(
            "receiver_safety:test_unimported_type_is_not_guessed_globally:111-4"
        ),
        ("local.persist()", False),
    )
