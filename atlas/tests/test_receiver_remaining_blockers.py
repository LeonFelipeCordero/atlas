"""Fresh-review receiver mutation, initializer and Rust owner regressions."""

from tests.resolution_snapshot_support import fixture_sources
import pytest
from tests.test_receiver_safety import assert_target


@pytest.mark.parametrize(
    "case",
    [
        (
            "javascript",
            "app.js",
            "alias-field-mutation-javascript-01",
            "this.service.persist()",
        ),
        (
            "typescript",
            "app.ts",
            "alias-field-mutation-typescript-01",
            "this.service.persist()",
        ),
        (
            "python",
            "app.py",
            "alias-field-mutation-python-01",
            "self.service.persist()",
        ),
        ("go", "app.go", "alias-field-mutation-go-01", "holder.service.persist()"),
        (
            "python",
            "app.py",
            "alias-field-mutation-python-02",
            "self.inner.service.persist()",
        ),
    ],
)
def test_alias_field_mutation(case):
    language, path, source, evidence = case
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_alias_field_mutation:17-4", case=case
        ),
        (evidence, False),
    )


@pytest.mark.parametrize(
    "language_case", [("javascript", "js"), ("typescript", "ts"), ("tsx", "tsx")]
)
@pytest.mark.parametrize("target", ["Alias.prototype.persist", "local.persist"])
@pytest.mark.parametrize(
    "operation",
    ["&&=replacement", "||=replacement", "??=replacement", "+=replacement", "++"],
)
def test_script_member_write_forms(language_case, target, operation):
    language, extension = language_case
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_script_member_write_forms:29-4",
            language_case=language_case,
            target=target,
            operation=operation,
        ),
        ("local.persist()", False),
    )


@pytest.mark.parametrize(
    "language,extension", [("python", "py"), ("typescript", "ts"), ("tsx", "tsx")]
)
@pytest.mark.parametrize("same", [False, True])
def test_annotated_constructor_initializer_identity(language, extension, same):
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_annotated_constructor_initializer_identity:38-4",
            language=language,
            same=same,
        ),
        ("local.persist()", same),
    )


@pytest.mark.parametrize(
    "language,extension", [("python", "py"), ("typescript", "ts"), ("tsx", "tsx")]
)
@pytest.mark.parametrize("same", [False, True])
def test_annotated_identifier_initializer_identity(language, extension, same):
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_annotated_identifier_initializer_identity:47-4",
            language=language,
            same=same,
        ),
        ("local.persist()", same),
    )


@pytest.mark.parametrize(
    "language,sources",
    [
        (
            "python",
            {
                "service.py": "import-alias-identity-and-static-parameter-types-python-01",
                "app.py": "import-alias-identity-and-static-parameter-types-python-01",
            },
        ),
        (
            "typescript",
            {
                "service.ts": "import-alias-identity-and-static-parameter-types-typescript-01",
                "app.ts": "import-alias-identity-and-static-parameter-types-typescript-01",
            },
        ),
        (
            "java",
            {"App.java": "import-alias-identity-and-static-parameter-types-java-01"},
        ),
        (
            "kotlin",
            {"app.kt": "import-alias-identity-and-static-parameter-types-kotlin-01"},
        ),
    ],
)
def test_import_alias_identity_and_static_parameter_types(language, sources):
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_import_alias_identity_and_static_parameter_types:57-4",
            language=language,
        ),
        ("local.persist()", True),
    )


@pytest.mark.parametrize("kind,declaration", [("struct", "{}"), ("enum", "{One}")])
@pytest.mark.parametrize("qualified", [False, True])
def test_rust_self_impl_identity(kind, declaration, qualified):
    assert_target(
        "rust",
        fixture_sources(
            "receiver_remaining_blockers:test_rust_self_impl_identity:66-4",
            kind=kind,
            qualified=qualified,
        ),
        ("self.persist()", True),
    )


@pytest.mark.parametrize(
    "language,path,source",
    [
        ("rust", "app.rs", "compound-receiver-assignment-rust-01"),
        ("go", "app.go", "compound-receiver-assignment-go-01"),
        ("go", "app.go", "compound-receiver-assignment-go-02"),
        ("java", "App.java", "compound-receiver-assignment-java-01"),
        ("kotlin", "app.kt", "compound-receiver-assignment-kotlin-01"),
        ("kotlin", "app.kt", "compound-receiver-assignment-kotlin-02"),
    ],
)
def test_compound_receiver_assignment(language, path, source):
    assert_target(
        language,
        fixture_sources(
            "receiver_remaining_blockers:test_compound_receiver_assignment:78-4",
            source=source,
        ),
        ("local.persist()", False),
    )
