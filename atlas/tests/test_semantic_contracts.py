"""End-to-end extraction/resolution contracts, with no injected source facts."""

from tests.resolution_snapshot_support import fixture_sources
from tests.test_semantic_resolution import ResolutionAssertions, call_edges, repository


class ExtractionContractTest(ResolutionAssertions):
    def test_macro_inner_calls_have_original_source_spans_and_hints(self):
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_contracts:test_macro_inner_calls_have_original_source_spans_and_hints:9-15"
            ),
        )
        file = repo.files[0]
        calls = [call for call in file.calls if call.name == "brew"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].start_byte, file.source.source.rindex(b"brew()"))
        self.assertEqual(calls[0].evidence, "brew()")
        self.assertIn("println!", {call.name for call in file.calls})

    def test_constructor_identity_never_uses_global_type_guessing(self):
        for language, extension, declaration, usage in [
            (
                "python",
                "py",
                "constructor-identity-never-uses-global-type-guessing-python-01",
                "Maker().brew()",
            ),
            (
                "typescript",
                "ts",
                "constructor-identity-never-uses-global-type-guessing-typescript-01",
                "new Maker().brew()",
            ),
        ]:
            with self.subTest(language=language):
                repo = repository(
                    language,
                    fixture_sources(
                        "semantic_contracts:test_constructor_identity_never_uses_global_type_guessing:35-23",
                        language=language,
                    ),
                )
                self.external(repo, usage)
                self.external(
                    repo, "Maker()" if language == "python" else "new Maker()"
                )

    def test_java_static_member_import(self):
        repo = repository(
            "java",
            fixture_sources("semantic_contracts:test_java_static_member_import:45-15"),
        )
        self.internal(repo, "portions(1)", "R.portions")

    def test_elixir_clause_arity_and_unrelated_modules_remain_ambiguous(self):
        repo = repository(
            "elixir",
            fixture_sources(
                "semantic_contracts:test_elixir_clause_arity_and_unrelated_modules_remain_ambiguous:55-15"
            ),
        )
        edges = call_edges(repo, "retry(n-1)")
        self.assertEqual(len(edges), 2)
        self.assertTrue(all(("Maker.retry" in e.target_key for e in edges)))
        other_arity = next(
            (
                s.key
                for s in repo.symbols
                if s.signature and "retry(n, x)" in s.signature
            )
        )
        self.assertNotIn(other_arity, {e.target_key for e in edges})

    def test_rust_object_dot_is_not_a_module_reference(self):
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_contracts:test_rust_object_dot_is_not_a_module_reference:71-15"
            ),
        )
        self.external(repo, "recipe.portions(1)")

    def test_receiver_rebinding_and_prototype_replacement(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_contracts:test_receiver_rebinding_and_prototype_replacement:81-15"
            ),
        )
        self.external(repo, "self.retry(n-1)")
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_contracts:test_receiver_rebinding_and_prototype_replacement:88-15"
            ),
        )
        self.external(repo, "new Maker().brew()")
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_contracts:test_receiver_rebinding_and_prototype_replacement:95-15"
            ),
        )
        self.external(repo, "new R().brew()")
