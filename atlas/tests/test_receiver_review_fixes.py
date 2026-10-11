"""Receiver review regressions: mutation safety and inherent impl identity."""

from tests.resolution_snapshot_support import fixture_sources
import pytest
from tests.test_receiver_safety import assert_target
from tests.test_semantic_resolution import call_edges, repository


@pytest.mark.parametrize(
    "language,path,source",
    [
        (
            "typescript",
            "app.ts",
            "reassigned-declared-receiver-is-not-trusted-typescript-01",
        ),
        ("tsx", "app.tsx", "reassigned-declared-receiver-is-not-trusted-typescript-01"),
        ("java", "App.java", "reassigned-declared-receiver-is-not-trusted-java-01"),
        ("kotlin", "App.kt", "reassigned-declared-receiver-is-not-trusted-kotlin-01"),
    ],
)
def test_reassigned_declared_receiver_is_not_trusted(language, path, source):
    assert_target(
        language,
        fixture_sources(
            "receiver_review_fixes:test_reassigned_declared_receiver_is_not_trusted:16-4",
            language=language,
        ),
        ("local.persist()", False),
    )


@pytest.mark.parametrize(
    "case",
    [
        (
            "python",
            "app.py",
            "caller-field-writes-invalidate-receiver-python-01",
            "holder.service.persist()",
        ),
        (
            "python",
            "app.py",
            "caller-field-writes-invalidate-receiver-python-02",
            "holder.service.persist()",
        ),
        (
            "python",
            "app.py",
            "caller-field-writes-invalidate-receiver-python-03",
            "holder.service.persist()",
        ),
        (
            "python",
            "app.py",
            "caller-field-writes-invalidate-receiver-python-04",
            "alias.service.persist()",
        ),
        (
            "python",
            "app.py",
            "caller-field-writes-invalidate-receiver-python-05",
            "holder.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "caller-field-writes-invalidate-receiver-javascript-01",
            "holder.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "caller-field-writes-invalidate-receiver-javascript-02",
            "holder.service.persist()",
        ),
    ],
)
def test_caller_field_writes_invalidate_receiver(case):
    language, path, source, evidence = case
    assert_target(
        language,
        fixture_sources(
            "receiver_review_fixes:test_caller_field_writes_invalidate_receiver:30-4",
            case=case,
        ),
        (evidence, False),
    )


@pytest.mark.parametrize(
    "language,sources",
    [
        (
            "python",
            {
                "tools.py": "import-alias-identity-and-static-parameter-types-python-01",
                "app.py": "member-mutation-follows-imported-class-identity-python-01",
            },
        ),
        (
            "typescript",
            {
                "tools.ts": "import-alias-identity-and-static-parameter-types-typescript-01",
                "app.ts": "member-mutation-follows-imported-class-identity-typescript-01",
            },
        ),
        (
            "tsx",
            {
                "tools.tsx": "import-alias-identity-and-static-parameter-types-typescript-01",
                "app.tsx": "member-mutation-follows-imported-class-identity-typescript-01",
            },
        ),
        (
            "python",
            {
                "tools.py": "import-alias-identity-and-static-parameter-types-python-01",
                "app.py": "member-mutation-follows-imported-class-identity-python-02",
            },
        ),
    ],
)
def test_member_mutation_follows_imported_class_identity(language, sources):
    assert_target(
        language,
        fixture_sources(
            "receiver_review_fixes:test_member_mutation_follows_imported_class_identity:40-4",
            sources=sources,
        ),
        ("local.persist()", False),
    )


@pytest.mark.parametrize(
    "case",
    [
        (
            "typescript",
            "app.ts",
            "unchanged-receivers-remain-internal-typescript-01",
            "local.persist()",
        ),
        (
            "tsx",
            "app.tsx",
            "unchanged-receivers-remain-internal-typescript-01",
            "local.persist()",
        ),
        (
            "python",
            "app.py",
            "unchanged-receivers-remain-internal-python-01",
            "holder.service.persist()",
        ),
        (
            "javascript",
            "app.js",
            "unchanged-receivers-remain-internal-javascript-01",
            "holder.service.persist()",
        ),
    ],
)
def test_unchanged_receivers_remain_internal(case):
    language, path, source, evidence = case
    assert_target(
        language,
        fixture_sources(
            "receiver_review_fixes:test_unchanged_receivers_remain_internal:51-4",
            case=case,
        ),
        (evidence, True),
    )


@pytest.mark.parametrize(
    "implementation",
    [
        "rust-impl-in-another-module-resolves-identity-rust-01",
        "rust-impl-in-another-module-resolves-identity-rust-02",
        "rust-impl-in-another-module-resolves-identity-rust-03",
    ],
)
def test_rust_impl_in_another_module_resolves_identity(implementation):
    assert_target(
        "rust",
        fixture_sources(
            "receiver_review_fixes:test_rust_impl_in_another_module_resolves_identity:62-4",
            implementation=implementation,
        ),
        ("local.persist()", True),
    )


def test_rust_same_short_name_impl_is_not_used():
    assert_target(
        "rust",
        fixture_sources(
            "receiver_review_fixes:test_rust_same_short_name_impl_is_not_used:71-4"
        ),
        ("local.persist()", False),
    )


def test_rust_duplicate_impl_members_are_ambiguous():
    assert_target(
        "rust",
        fixture_sources(
            "receiver_review_fixes:test_rust_duplicate_impl_members_are_ambiguous:79-4"
        ),
        ("local.persist()", False),
    )


def test_rust_trait_impl_is_not_an_inherent_member():
    assert_target(
        "rust",
        fixture_sources(
            "receiver_review_fixes:test_rust_trait_impl_is_not_an_inherent_member:87-4"
        ),
        ("local.persist()", False),
    )


def test_java_constructor_subtype_field_write_is_not_trusted():
    assert_target(
        "java",
        fixture_sources(
            "receiver_review_fixes:test_java_constructor_subtype_field_write_is_not_trusted:92-4"
        ),
        ("local.persist()", False),
    )


def test_rust_impl_target_is_the_actual_method():
    repo = repository(
        "rust",
        fixture_sources(
            "receiver_review_fixes:test_rust_impl_target_is_the_actual_method:98-11"
        ),
    )
    edges = call_edges(repo, "local.persist()")
    targets = {symbol.key: symbol for symbol in repo.symbols}
    assert len(edges) == 1
    target = targets[edges[0].target_key]
    assert (target.file_path, target.name) == ("main.rs", "persist")
